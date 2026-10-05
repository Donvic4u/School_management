from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import (
    AcademicSession,
    ClassLevel,
    Enrollment,
    GradeScale,
    Score,
    SchoolProfile,
    Student,
    Term,
    ResultPublication,
)


def get_current_term():
    term = (
        Term.objects
        .filter(is_current=True)
        .select_related("session")
        .first()
    )

    if term:
        return term

    session = (
        AcademicSession.objects
        .filter(is_current=True)
        .first()
    )

    if session:
        return (
            Term.objects
            .filter(session=session)
            .order_by("id")
            .first()
        )

    return Term.objects.select_related("session").order_by("-session__id", "id").first()


def get_grade(total):
    """
    Find the grade and remark from the school's GradeScale.
    """
    if total is None:
        return "", ""

    grade_scale = (
        GradeScale.objects
        .filter(
            minimum_score__lte=total,
            maximum_score__gte=total,
        )
        .first()
    )

    if grade_scale:
        return grade_scale.grade, grade_scale.remark

    return "", ""


def competition_rank(values):
    """
    Competition ranking:
    100, 100, 90, 80 -> 1, 1, 3, 4
    """
    ranks = {}
    previous = None
    current_rank = 0

    for index, value in enumerate(values, start=1):
        if value != previous:
            current_rank = index
            previous = value

        ranks[value] = current_rank

    return ranks


def build_class_results(class_level, term):
    """
    Build official result data for all students in a class.

    Only approved scores are used.
    """

    enrollments = list(
        Enrollment.objects
        .filter(
            class_level=class_level,
            term=term,
        )
        .select_related("student", "class_level", "term")
        .order_by(
            "student__surname",
            "student__first_name",
            "student__other_names",
        )
    )

    subjects = list(
        Score.objects
        .filter(
            enrollment__in=enrollments,
            approved=True,
        )
        .select_related("subject")
        .values_list("subject", flat=False)
        .distinct()
    )

    # The values_list above returns model instances only when using
    # values_list incorrectly, so use the actual subject queryset below.
    subjects = list(
        Score.objects
        .filter(
            enrollment__in=enrollments,
            approved=True,
        )
        .select_related("subject")
        .values(
            "subject_id",
            "subject__code",
            "subject__name",
        )
        .distinct()
        .order_by("subject__name")
    )

    subject_ids = [item["subject_id"] for item in subjects]

    score_records = (
        Score.objects
        .filter(
            enrollment__in=enrollments,
            subject_id__in=subject_ids,
            approved=True,
        )
        .select_related("subject", "enrollment")
    )

    score_map = {
        (score.enrollment_id, score.subject_id): score
        for score in score_records
    }

    # Calculate subject positions.
    subject_positions = {}

    for subject in subjects:
        totals = []

        for enrollment in enrollments:
            score = score_map.get(
                (enrollment.id, subject["subject_id"])
            )

            if score is not None:
                totals.append((
                    enrollment.id,
                    Decimal(str(score.total)),
                ))

        sorted_totals = sorted(
            [total for _, total in totals],
            reverse=True,
        )

        rank_map = competition_rank(sorted_totals)

        subject_positions[subject["subject_id"]] = {
            enrollment_id: rank_map[total]
            for enrollment_id, total in totals
        }

    students = []

    overall_values = []

    for enrollment in enrollments:
        subject_results = []
        total_marks = Decimal("0")
        completed_subjects = 0

        for subject in subjects:
            score = score_map.get(
                (enrollment.id, subject["subject_id"])
            )

            if score is None:
                subject_results.append({
                    "subject": subject,
                    "ca1": None,
                    "ca2": None,
                    "ca3": None,
                    "ca_total": None,
                    "exam": None,
                    "total": None,
                    "grade": "",
                    "remark": "",
                    "position": "",
                    "approved": False,
                })
                continue

            total = Decimal(str(score.total))
            grade, remark = get_grade(total)

            total_marks += total
            completed_subjects += 1

            subject_results.append({
                "subject": subject,
                "ca1": score.ca1_score,
                "ca2": score.ca2_score,
                "ca3": score.ca3_score,
                "ca_total": score.ca_total,
                "exam": score.exam_score,
                "total": total,
                "grade": grade,
                "remark": remark,
                "position": subject_positions.get(
                    subject["subject_id"], {}
                ).get(enrollment.id, ""),
                "approved": True,
            })

        average = (
            total_marks / completed_subjects
            if completed_subjects
            else Decimal("0")
        )

        overall_values.append((
            enrollment.id,
            total_marks,
            average,
            completed_subjects,
        ))

        students.append({
            "enrollment": enrollment,
            "student": enrollment.student,
            "subjects": subject_results,
            "total_marks": total_marks,
            "average": average,
            "completed_subjects": completed_subjects,
            "total_subjects": len(subjects),
            "complete": (
                completed_subjects == len(subjects)
                if subjects
                else False
            ),
        })

    # Overall position is based on average.
    # If averages are equal, total marks is used as the tie-breaker.
    sorted_overall = sorted(
        overall_values,
        key=lambda item: (item[2], item[1]),
        reverse=True,
    )

    overall_rank_values = [
        (item[2], item[1])
        for item in sorted_overall
    ]

    overall_rank_map = {}
    previous = None
    current_rank = 0

    for index, value in enumerate(overall_rank_values, start=1):
        if value != previous:
            current_rank = index
            previous = value

        overall_rank_map[value] = current_rank

    for student_data in students:
        key = (
            student_data["average"],
            student_data["total_marks"],
        )
        student_data["position"] = overall_rank_map.get(key, "")

        grade, remark = get_grade(student_data["average"])
        student_data["overall_grade"] = grade
        student_data["overall_remark"] = remark

    return {
        "class_level": class_level,
        "term": term,
        "subjects": subjects,
        "students": students,
    }


@login_required(login_url="/teacher-login/")
def class_master_result(request, class_id):
    class_level = get_object_or_404(
        ClassLevel,
        id=class_id,
    )

    term = get_current_term()

    if term is None:
        return render(
            request,
            "master_result.html",
            {
                "class_level": class_level,
                "term": None,
                "subjects": [],
                "students": [],
                "error": "No academic term has been configured.",
            },
        )

    publication = ResultPublication.objects.filter(
        session=term.session,
        term=term,
        class_level=class_level,
        published=True,
    ).first()

    if publication is None:
        return render(
            request,
            "master_result.html",
            {
                "class_level": class_level,
                "term": term,
                "subjects": [],
                "students": [],
                "error": "This result has not been published yet.",
            },
        )

    result = build_class_results(
        class_level,
        term,
    )

    result["publication"] = publication

    return render(
        request,
        "master_result.html",
        result,
    )


@login_required(login_url="/teacher-login/")
def student_result(request, student_id):
    student = get_object_or_404(
        Student,
        id=student_id,
    )

    term = get_current_term()

    enrollment = (
        Enrollment.objects
        .filter(
            student=student,
            term=term,
        )
        .select_related(
            "class_level",
            "term",
        )
        .first()
    )

    if not enrollment:
        return render(
            request,
            "school/student_result.html",
            {
                "student": student,
                "enrollment": None,
                "term": term,
                "results": [],
                "summary": {},
                "school": SchoolProfile.objects.first(),
                "form_teacher_remark": "",
                "principal_remark": "",
                "result_reference": "",
                "published": False,
                "error": "No result enrollment was found for this term.",
            },
        )

    publication = ResultPublication.objects.filter(
        session=term.session,
        term=term,
        class_level=enrollment.class_level,
        published=True,
    ).first()

    if publication is None:
        return render(
            request,
            "school/student_result.html",
            {
                "student": student,
                "enrollment": enrollment,
                "term": term,
                "results": [],
                "summary": {},
                "school": SchoolProfile.objects.first(),
                "form_teacher_remark": "",
                "principal_remark": "",
                "result_reference": "",
                "published": False,
                "error": "This result has not been published yet.",
            },
        )

    class_results = build_class_results(
        enrollment.class_level,
        term,
    )

    student_data = next(
        (
            item
            for item in class_results["students"]
            if item["student"].id == student.id
        ),
        None,
    )

    if student_data is None:
        results = []
        summary = {}
    else:
        results = student_data.get("subjects", [])

        summary = {
            "total_marks": student_data.get("total_marks", 0),
            "average": student_data.get("average", 0),
            "overall_grade": student_data.get("overall_grade", ""),
            "overall_remark": student_data.get("overall_remark", ""),
            "position": student_data.get("position", ""),
            "completed_subjects": student_data.get("completed_subjects", 0),
            "total_subjects": student_data.get("total_subjects", 0),
        }

    session_code = str(term.session.name).replace("/", "")
    term_code = str(term.name).strip().upper().replace(" ", "")[:3]

    result_reference = (
        f"{student.admission_number}-{session_code}-{term_code}"
    )

    return render(
        request,
        "school/student_result.html",
        {
            "student": student,
            "enrollment": enrollment,
            "term": term,
            "results": results,
            "summary": summary,
            "school": SchoolProfile.objects.first(),
            "form_teacher_remark": dict(
                Enrollment.FORM_TEACHER_COMMENT_CHOICES
            ).get(
                enrollment.form_teacher_comment,
                enrollment.form_teacher_comment or "",
            ),
            "principal_remark": dict(
                Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
            ).get(
                enrollment.academic_performance_comment,
                enrollment.academic_performance_comment or "",
            ),
            "result_reference": result_reference,
            "published": True,
            "publication": publication,
        },
    )

def result_dashboard(request):
    from .models import (
        ClassLevel,
        Enrollment,
        Score,
        AcademicSession,
        Term,
        ResultPublication,
    )

    sessions = AcademicSession.objects.all().order_by("-name")

    selected_session_id = request.GET.get("session")
    selected_term_id = request.GET.get("term")
    selected_class_id = request.GET.get("class")
    selected_status = request.GET.get("status", "")

    # ---------------------------------------------
    # Academic session
    # ---------------------------------------------
    if selected_session_id:
        selected_session = sessions.filter(
            id=selected_session_id
        ).first()
    else:
        selected_session = sessions.filter(
            is_current=True
        ).first()

    if selected_session is None:
        selected_session = sessions.first()

    # ---------------------------------------------
    # Terms
    # ---------------------------------------------
    terms = Term.objects.none()

    if selected_session:
        terms = Term.objects.filter(
            session=selected_session
        ).order_by("id")

    if selected_term_id:
        selected_term = terms.filter(
            id=selected_term_id
        ).first()
    else:
        selected_term = terms.filter(
            is_current=True
        ).first()

    if selected_term is None:
        selected_term = terms.first()

    # ---------------------------------------------
    # Classes
    # ---------------------------------------------
    classes = ClassLevel.objects.all().order_by("name")

    class_data = []

    for class_level in classes:

        # Class filter
        if selected_class_id:
            if str(class_level.id) != str(selected_class_id):
                continue

        enrollments = Enrollment.objects.filter(
            class_level=class_level,
            term=selected_term,
        ).select_related("student")

        scores = Score.objects.filter(
            enrollment__in=enrollments,
        )

        total_scores = scores.count()

        submitted_scores = scores.filter(
            submitted=True
        ).count()

        approved_scores = scores.filter(
            approved=True
        ).count()

        # ---------------------------------------------
        # Determine workflow status
        # ---------------------------------------------
        if total_scores == 0:
            status = "Not Started"

        elif approved_scores == total_scores:
            status = "Approved / Locked"

        elif submitted_scores == total_scores:
            status = "Awaiting Approval"

        elif submitted_scores > 0:
            status = "Partially Submitted"

        else:
            status = "In Progress"

        # ---------------------------------------------
        # Publication status
        # ---------------------------------------------
        publication = None

        if selected_session and selected_term:
            publication = ResultPublication.objects.filter(
                session=selected_session,
                term=selected_term,
                class_level=class_level,
            ).first()

        if publication and publication.published:
            publication_status = "Published"
        else:
            publication_status = "Not Published"

        # ---------------------------------------------
        # Combined dashboard status
        # ---------------------------------------------
        if publication_status == "Published":
            display_status = "Published"
        else:
            display_status = status

        # Status filter
        if selected_status:
            if selected_status == "Published":
                if publication_status != "Published":
                    continue
            elif display_status != selected_status:
                continue

        # ---------------------------------------------
        # Student links
        # ---------------------------------------------
        students = []

        for enrollment in enrollments:
            students.append({
                "student": enrollment.student,
                "url_id": enrollment.student.id,
            })

        class_data.append({
            "class_level": class_level,
            "student_count": enrollments.count(),
            "total_scores": total_scores,
            "submitted_scores": submitted_scores,
            "approved_scores": approved_scores,
            "status": display_status,
            "workflow_status": status,
            "publication_status": publication_status,
            "published_at": (
                publication.published_at
                if publication and publication.published
                else None
            ),
            "students": students,
        })

    status_choices = [
        "Not Started",
        "In Progress",
        "Partially Submitted",
        "Awaiting Approval",
        "Approved / Locked",
        "Published",
    ]

    context = {
        "sessions": sessions,
        "terms": terms,
        "classes": classes,
        "selected_session": selected_session,
        "selected_term": selected_term,
        "selected_class_id": selected_class_id,
        "selected_status": selected_status,
        "status_choices": status_choices,
        "class_data": class_data,
    }

    return render(
        request,
        "school/result_dashboard.html",
        context,
    )
