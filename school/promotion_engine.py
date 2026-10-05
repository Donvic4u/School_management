from decimal import Decimal
from django.db import transaction

from .models import (
    AcademicSession,
    ClassLevel,
    Enrollment,
    Score,
    Subject,
    Term,
)


# ============================================================
# AUTOMATIC PROMOTION RULES
# ============================================================

MINIMUM_AVERAGE = Decimal("50.00")
MINIMUM_GRADE_FOR_CORE_SUBJECTS = "C"
MAX_JSS_FAILED_SUBJECTS = 4


SSS_SCIENCE_CORE_SUBJECTS = [
    "Mathematics",
    "English Language",
    "Physics",
    "Chemistry",
    "Biology",
]

SSS_ART_CORE_SUBJECTS = [
    "English Language",
    "Government",
    "Literature-in-English",
    "Economics",
]


# ============================================================
# GRADE CALCULATION
# ============================================================

def get_grade(score):
    """
    Return the school's grade for a score.

    Current school scale:
    A = 70-100
    B = 60-69
    C = 50-59
    D = 40-49
    F = 0-39
    """

    try:
        value = Decimal(str(score))
    except (TypeError, ValueError):
        return None

    if Decimal("70") <= value <= Decimal("100"):
        return "A"

    if Decimal("60") <= value < Decimal("70"):
        return "B"

    if Decimal("50") <= value < Decimal("60"):
        return "C"

    if Decimal("40") <= value < Decimal("50"):
        return "D"

    if Decimal("0") <= value < Decimal("40"):
        return "F"

    return None


# ============================================================
# CLASS TYPE
# ============================================================

def get_class_category(class_name):
    """
    Determine whether a class is JSS, SSS Science or SSS Art.

    Science/Art is determined from the class letter:
        A = Science
        B = Art

    Example:
        SSS 1A -> SSS Science
        SSS 1B -> SSS Art
    """

    name = class_name.strip().upper()

    if name.startswith("JSS"):
        return "JSS"

    if name.startswith("SSS"):
        if name.endswith("A"):
            return "SSS_SCIENCE"

        if name.endswith("B"):
            return "SSS_ART"

    return None


# ============================================================
# RESULT EVALUATION
# ============================================================

def evaluate_student(enrollment):
    """
    Evaluate one student's promotion eligibility.

    Only APPROVED scores are considered.

    Returns a dictionary containing:
        eligible
        category
        average
        failed_subjects
        core_subjects
        reasons
    """

    student = enrollment.student
    class_level = enrollment.class_level

    category = get_class_category(class_level.name)

    if category is None:
        return {
            "eligible": False,
            "category": None,
            "average": None,
            "failed_subjects": [],
            "core_subjects": {},
            "reasons": ["Class type could not be determined."],
        }

    scores = list(
        Score.objects
        .filter(
            enrollment=enrollment,
            approved=True,
        )
        .select_related("subject")
    )

    if not scores:
        return {
            "eligible": False,
            "category": category,
            "average": None,
            "failed_subjects": [],
            "core_subjects": {},
            "reasons": ["No approved scores are available."],
        }

    # --------------------------------------------------------
    # Expected subjects
    # --------------------------------------------------------

    expected_subject_ids = set(
        class_level.class_subjects
        .filter(active=True)
        .values_list("subject_id", flat=True)
    )

    approved_subject_ids = {score.subject_id for score in scores}

    missing_subject_ids = expected_subject_ids - approved_subject_ids

    if missing_subject_ids:
        missing_names = list(
            Subject.objects
            .filter(id__in=missing_subject_ids)
            .order_by("name")
            .values_list("name", flat=True)
        )
    else:
        missing_names = []

    # Do not evaluate an incomplete result.
    if missing_names:
        return {
            "eligible": False,
            "category": category,
            "average": None,
            "failed_subjects": [],
            "core_subjects": {},
            "reasons": [
                "Result is incomplete. Missing approved scores: "
                + ", ".join(missing_names)
            ],
        }

    # --------------------------------------------------------
    # Calculate average
    # --------------------------------------------------------

    totals = [Decimal(str(score.total)) for score in scores]

    average = (
        sum(totals) / Decimal(len(totals))
        if totals
        else Decimal("0")
    )

    average = average.quantize(Decimal("0.01"))

    reasons = []

    if average < MINIMUM_AVERAGE:
        reasons.append(
            f"Overall average is {average}%, below the required 50%."
        )

    # --------------------------------------------------------
    # JSS RULE
    # --------------------------------------------------------

    failed_subjects = []

    if category == "JSS":

        for score in scores:
            if Decimal(str(score.total)) < MINIMUM_AVERAGE:
                failed_subjects.append({
                    "subject": score.subject.name,
                    "total": Decimal(str(score.total)),
                    "grade": get_grade(score.total),
                })

        if len(failed_subjects) > MAX_JSS_FAILED_SUBJECTS:
            reasons.append(
                f"Student failed {len(failed_subjects)} subjects. "
                f"Maximum allowed is {MAX_JSS_FAILED_SUBJECTS}."
            )

    # --------------------------------------------------------
    # SSS SCIENCE / ART RULE
    # --------------------------------------------------------

    core_subject_names = []

    if category == "SSS_SCIENCE":
        core_subject_names = SSS_SCIENCE_CORE_SUBJECTS

    elif category == "SSS_ART":
        core_subject_names = SSS_ART_CORE_SUBJECTS

    score_by_subject = {
        score.subject.name.strip().lower(): score
        for score in scores
    }

    core_subjects = {}

    for subject_name in core_subject_names:

        score = score_by_subject.get(subject_name.strip().lower())

        if score is None:
            core_subjects[subject_name] = {
                "total": None,
                "grade": None,
                "qualified": False,
            }

            reasons.append(
                f"{subject_name} has no approved result."
            )

            continue

        total = Decimal(str(score.total))
        grade = get_grade(total)

        qualified = grade in {"A", "B", "C"}

        core_subjects[subject_name] = {
            "total": total,
            "grade": grade,
            "qualified": qualified,
        }

        if not qualified:
            reasons.append(
                f"{subject_name}: Grade {grade}; "
                "minimum required grade is C."
            )

    # --------------------------------------------------------
    # FINAL ELIGIBILITY
    # --------------------------------------------------------

    eligible = len(reasons) == 0

    return {
        "eligible": eligible,
        "category": category,
        "average": average,
        "failed_subjects": failed_subjects,
        "core_subjects": core_subjects,
        "reasons": reasons,
    }


# ============================================================
# NEXT CLASS
# ============================================================

def get_next_class(class_level):
    """
    Return the next class in the same arm.

    Examples:
        JSS 1A -> JSS 2A
        JSS 2A -> JSS 3A
        SSS 1A -> SSS 2A
        SSS 2A -> SSS 3A

    SSS3 has no next class and therefore returns None.
    """

    name = class_level.name.strip().upper()

    mapping = {
        "JSS 1A": "JSS 2A",
        "JSS 1B": "JSS 2B",
        "JSS 2A": "JSS 3A",
        "JSS 2B": "JSS 3B",
        "JSS 3A": None,
        "JSS 3B": None,

        "SSS 1A": "SSS 2A",
        "SSS 1B": "SSS 2B",
        "SSS 2A": "SSS 3A",
        "SSS 2B": "SSS 3B",
        "SSS 3A": None,
        "SSS 3B": None,
    }

    next_class_name = mapping.get(name)

    if not next_class_name:
        return None

    return ClassLevel.objects.filter(
        name__iexact=next_class_name
    ).first()


# ============================================================
# NEXT ACADEMIC SESSION
# ============================================================

def get_next_session(source_session):
    """
    Find the next academic session.

    The function expects sessions to use the format:
        2026/2027
        2027/2028
        2028/2029

    Returns None when the next session has not yet been created.
    """

    try:
        start_year = int(source_session.name[:4])
    except (ValueError, TypeError):
        return None

    next_session_name = f"{start_year + 1}/{start_year + 2}"

    return AcademicSession.objects.filter(
        name=next_session_name
    ).first()


# ============================================================
# AUTOMATIC PROMOTION PREVIEW
# ============================================================

def evaluate_term(term):
    """
    Evaluate every active student enrolled in a term.

    IMPORTANT:
    This function DOES NOT create enrollments or modify students.

    It is deliberately a preview/evaluation stage.
    """

    enrollments = (
        Enrollment.objects
        .filter(
            term=term,
            student__active=True,
        )
        .select_related(
            "student",
            "class_level",
            "term",
        )
        .order_by(
            "class_level__name",
            "student__surname",
            "student__first_name",
        )
    )

    results = []

    for enrollment in enrollments:

        evaluation = evaluate_student(enrollment)

        next_class = get_next_class(enrollment.class_level)

        next_session = get_next_session(term.session)

        if evaluation["eligible"]:

            if next_class is None:
                destination = "COMPLETED SSS3 / NO NEXT CLASS"

            elif next_session is None:
                destination = (
                    f"{next_class.name} — NEXT SESSION NOT CREATED"
                )

            else:
                destination = (
                    f"{next_class.name} — {next_session.name}"
                )

        else:
            destination = "NOT ELIGIBLE"

        results.append({
            "student": enrollment.student.full_name,
            "admission_number": enrollment.student.admission_number,
            "current_class": enrollment.class_level.name,
            "category": evaluation["category"],
            "average": evaluation["average"],
            "eligible": evaluation["eligible"],
            "failed_subjects": evaluation["failed_subjects"],
            "core_subjects": evaluation["core_subjects"],
            "reasons": evaluation["reasons"],
            "destination": destination,
        })

    return results


# ============================================================
# ACTUAL AUTOMATIC PROMOTION
# ============================================================

@transaction.atomic
def promote_term(term):
    """
    Automatically promote every eligible student.

    This function should only be called after Third Term
    results have been fully approved.

    Historical enrollments and scores are NEVER modified.
    """

    next_session = get_next_session(term.session)

    if next_session is None:
        raise ValueError(
            f"Next academic session for {term.session.name} "
            "has not been created."
        )

    destination_term = Term.objects.filter(
        session=next_session,
        name=Term.FIRST,
    ).first()

    if destination_term is None:
        raise ValueError(
            f"First Term for {next_session.name} has not been created."
        )

    results = evaluate_term(term)

    promoted = []
    completed = []
    not_promoted = []

    for result in results:

        if not result["eligible"]:
            not_promoted.append(result)
            continue

        current_class = ClassLevel.objects.get(
            name=result["current_class"]
        )

        next_class = get_next_class(current_class)

        # ----------------------------------------------------
        # SSS3 completion
        # ----------------------------------------------------

        if next_class is None:

            if result["current_class"] in {
                "SSS 3A",
                "SSS 3B",
            }:
                completed.append(result)

            else:
                not_promoted.append(result)

            continue

        # ----------------------------------------------------
        # Normal promotion
        # ----------------------------------------------------

        student = Enrollment.objects.get(
            student__admission_number=result["admission_number"],
            term=term,
        ).student

        already_enrolled = Enrollment.objects.filter(
            student=student,
            term=destination_term,
        ).exists()

        if already_enrolled:
            continue

        Enrollment.objects.create(
            student=student,
            class_level=next_class,
            term=destination_term,
        )

        student.current_class = next_class
        student.save(update_fields=["current_class"])

        promoted.append({
            **result,
            "destination": f"{next_class.name} — {next_session.name}",
        })

    return {
        "promoted": promoted,
        "completed": completed,
        "not_promoted": not_promoted,
        "destination_session": next_session.name,
        "destination_term": destination_term.name,
    }
