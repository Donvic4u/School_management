from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    StudentForm,
    StudentSearchForm,
    TeacherForm,
    SubjectForm,
    ClassTeacherForm,
    EnrollmentForm,
)
from .models import (
    SchoolProfile,
    AcademicSession,
    Term,
    ClassLevel,
    Subject,
    Teacher,
    Student,
    Enrollment,
    Score,
    GradeScale,
    TeacherAccount,
    TeachingAssignment,
    ClassSubject,
)



def academic_session_management(request):
    """
    Manage academic sessions and their terms.

    Creating a session automatically creates First, Second and Third Term.
    Only one academic session can be current.
    Only one term within a session can be current.
    """

    if not request.user.is_authenticated:
        return redirect("admin:login")

    if not request.user.is_staff:
        messages.error(
            request,
            "You do not have permission to manage academic sessions."
        )
        return redirect("dashboard")

    if request.method == "POST":

        action = request.POST.get("action")

        # ----------------------------------------------------
        # CREATE NEW SESSION
        # ----------------------------------------------------

        if action == "create_session":

            session_name = request.POST.get(
                "session_name",
                ""
            ).strip()

            if not session_name:
                messages.error(
                    request,
                    "Enter an academic session."
                )

            elif AcademicSession.objects.filter(
                name=session_name
            ).exists():

                messages.error(
                    request,
                    f"Academic session {session_name} already exists."
                )

            else:

                session = AcademicSession.objects.create(
                    name=session_name,
                    is_current=False
                )

                Term.objects.bulk_create([
                    Term(
                        session=session,
                        name=Term.FIRST,
                        is_current=False
                    ),
                    Term(
                        session=session,
                        name=Term.SECOND,
                        is_current=False
                    ),
                    Term(
                        session=session,
                        name=Term.THIRD,
                        is_current=False
                    ),
                ])

                messages.success(
                    request,
                    f"{session_name} created with First, Second and Third Term."
                )

            return redirect("academic_session_management")

        # ----------------------------------------------------
        # SET CURRENT SESSION
        # ----------------------------------------------------

        if action == "set_current_session":

            session_id = request.POST.get(
                "session_id"
            )

            session = get_object_or_404(
                AcademicSession,
                id=session_id
            )

            session.is_current = True
            session.save()

            messages.success(
                request,
                f"{session.name} is now the current academic session."
            )

            return redirect("academic_session_management")

        # ----------------------------------------------------
        # SET CURRENT TERM
        # ----------------------------------------------------

        if action == "set_current_term":

            term_id = request.POST.get(
                "term_id"
            )

            term = get_object_or_404(
                Term,
                id=term_id
            )

            term.is_current = True
            term.save()

            messages.success(
                request,
                f"{term.name} is now the current term for {term.session.name}."
            )

            return redirect("academic_session_management")

    sessions = (
        AcademicSession.objects
        .prefetch_related("terms")
        .order_by("-id")
    )

    current_session = (
        AcademicSession.objects
        .filter(is_current=True)
        .first()
    )

    current_term = (
        Term.objects
        .filter(is_current=True)
        .select_related("session")
        .first()
    )

    context = {
        "sessions": sessions,
        "current_session": current_session,
        "current_term": current_term,
    }

    return render(
        request,
        "school/academic_session_management.html",
        context
    )


def student_promotion(request):
    """
    Read-only automatic promotion status page.

    Students are NOT manually promoted from this page.
    Automatic promotion is triggered when eligible Third Term
    scores are approved through the score approval workflow.
    """

    from .promotion_engine import (
        evaluate_student,
        get_next_class,
        get_next_session,
    )

    sessions = AcademicSession.objects.all().order_by("-id")

    # --------------------------------------------------------
    # Select session.
    # --------------------------------------------------------

    session_id = request.GET.get("session")

    if session_id:
        selected_session = get_object_or_404(
            AcademicSession,
            id=session_id,
        )
    else:
        selected_session = (
            AcademicSession.objects
            .filter(is_current=True)
            .first()
            or AcademicSession.objects.order_by("-id").first()
        )

    # --------------------------------------------------------
    # Select term.
    # --------------------------------------------------------

    term_id = request.GET.get("term")

    if term_id and selected_session:
        selected_term = get_object_or_404(
            Term,
            id=term_id,
            session=selected_session,
        )
    else:
        selected_term = None

        if selected_session:
            selected_term = (
                Term.objects
                .filter(
                    session=selected_session,
                    name=Term.THIRD,
                )
                .first()
            )

            if selected_term is None:
                selected_term = (
                    Term.objects
                    .filter(session=selected_session)
                    .order_by("-id")
                    .first()
                )

    # --------------------------------------------------------
    # Evaluate students.
    # --------------------------------------------------------

    promotion_results = []

    if selected_term:

        enrollments = (
            Enrollment.objects
            .filter(term=selected_term)
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

        for enrollment in enrollments:

            evaluation = evaluate_student(enrollment)

            next_class = get_next_class(
                enrollment.class_level
            )

            next_session = get_next_session(
                enrollment.term.session
            )

            if enrollment.class_level.name in {
                "SSS 3A",
                "SSS 3B",
            } and evaluation["eligible"]:

                destination = "COMPLETED SSS3"

            elif evaluation["eligible"] and next_class:

                if next_session:
                    destination = next_class.name
                else:
                    destination = (
                        f"{next_class.name} "
                        "(WAITING FOR NEXT SESSION)"
                    )

            elif evaluation["eligible"]:

                destination = "NO DESTINATION"

            else:
                destination = "NOT ELIGIBLE"

            promotion_results.append({
                "enrollment": enrollment,
                "evaluation": evaluation,
                "destination": destination,
                "next_session": next_session,
            })

    total_students = len(promotion_results)
    eligible_count = sum(
        1 for item in promotion_results
        if item["evaluation"]["eligible"]
    )
    not_eligible_count = sum(
        1 for item in promotion_results
        if not item["evaluation"]["eligible"]
    )
    waiting_count = sum(
        1
        for item in promotion_results
        if "WAITING FOR NEXT SESSION" in item["destination"]
    )
    completed_sss3_count = sum(
        1
        for item in promotion_results
        if item["destination"] == "COMPLETED SSS3"
    )

    context = {
        "sessions": sessions,
        "selected_session": selected_session,
        "selected_term": selected_term,
        "terms": (
            Term.objects
            .filter(session=selected_session)
            .order_by("id")
            if selected_session
            else Term.objects.none()
        ),
        "promotion_results": promotion_results,
        "total_students": total_students,
        "eligible_count": eligible_count,
        "not_eligible_count": not_eligible_count,
        "waiting_count": waiting_count,
        "completed_sss3_count": completed_sss3_count,
    }

    return render(
        request,
        "school/student_promotion.html",
        context,
    )

def dashboard(request):
    school = SchoolProfile.objects.first()

    current_session = (
        AcademicSession.objects
        .filter(is_current=True)
        .first()
    )

    current_term = (
        Term.objects
        .filter(
            session=current_session,
            is_current=True,
        )
        .first()
        if current_session
        else None
    )

    total_students = Student.objects.count()

    active_students = Student.objects.filter(
        active=True
    ).count()

    total_teachers = Teacher.objects.count()

    active_teachers = Teacher.objects.filter(
        active=True
    ).count()

    total_classes = ClassLevel.objects.count()

    classes_with_form_teachers = ClassLevel.objects.filter(
        form_teacher__isnull=False
    ).count()

    classes_without_form_teachers = (
        total_classes - classes_with_form_teachers
    )

    active_subjects = Subject.objects.filter(
        active=True
    ).count()

    approved_scores = Score.objects.filter(
        approved=True
    ).count()

    submitted_pending_scores = Score.objects.filter(
        submitted=True,
        approved=False,
    ).count()

    total_score_records = Score.objects.count()

    context = {
        "school": school,

        "current_session": current_session,
        "current_term": current_term,

        "total_students": total_students,
        "active_students": active_students,

        "total_teachers": total_teachers,
        "active_teachers": active_teachers,

        "total_classes": total_classes,
        "classes_with_form_teachers": classes_with_form_teachers,
        "classes_without_form_teachers": classes_without_form_teachers,

        "active_subjects": active_subjects,

        "approved_scores": approved_scores,
        "submitted_pending_scores": submitted_pending_scores,
        "total_score_records": total_score_records,
    }

    return render(
        request,
        "school/dashboard.html",
        context,
    )

def student_list(request):
    from django.db.models import Q

    form = StudentSearchForm(request.GET or None)

    students = (
        Student.objects
        .order_by("surname", "first_name")
    )

    if form.is_valid():
        search = form.cleaned_data.get("search")
        class_level = form.cleaned_data.get("class_level")
        gender = form.cleaned_data.get("gender")
        active = form.cleaned_data.get("active")

        if search:
            students = students.filter(
                Q(admission_number__icontains=search)
                | Q(surname__icontains=search)
                | Q(first_name__icontains=search)
                | Q(other_names__icontains=search)
            )

        if class_level:
            students = students.filter(
                enrollments__class_level=class_level,
                enrollments__term__is_current=True,
            )

        if gender:
            students = students.filter(gender=gender)

        if active:
            students = students.filter(active=True)

    current_term = Term.objects.filter(
        is_current=True
    ).select_related("session").first()

    class_categories = []

    if current_term:
        for class_level in ClassLevel.objects.all().order_by("name"):
            class_students = students.filter(
                enrollments__class_level=class_level,
                enrollments__term=current_term,
            ).distinct().order_by("surname", "first_name")

            class_categories.append({
                "class_level": class_level,
                "students": class_students,
                "count": class_students.count(),
            })

        enrolled_student_ids = Enrollment.objects.filter(
            term=current_term
        ).values_list("student_id", flat=True)

        unassigned_students = students.exclude(
            id__in=enrolled_student_ids
        )
    else:
        for class_level in ClassLevel.objects.all().order_by("name"):
            class_students = students.filter(
                current_class=class_level
            )

            class_categories.append({
                "class_level": class_level,
                "students": class_students,
                "count": class_students.count(),
            })

        unassigned_students = students.filter(
            current_class__isnull=True
        )

    jss_classes = [
        item for item in class_categories
        if item["class_level"].name.startswith("JSS")
    ]

    sss_classes = [
        item for item in class_categories
        if item["class_level"].name.startswith("SSS")
    ]

    return render(
        request,
        "school/student_list.html",
        {
            "form": form,
            "jss_classes": jss_classes,
            "sss_classes": sss_classes,
            "unassigned_students": unassigned_students,
        },
    )

def student_add(request):
    if request.method == "POST":
        form = StudentForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Student added successfully.")
            return redirect("student_list")
    else:
        form = StudentForm()

    return render(
        request,
        "school/student_form.html",
        {
            "form": form,
            "title": "Add Student",
        },
    )




def enrollment_management(request):
    """
    Manage student academic enrollments without altering historical records.
    """

    if not request.user.is_authenticated:
        return redirect("admin:login")

    if not request.user.is_staff:
        messages.error(
            request,
            "You do not have permission to manage student enrollments."
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = EnrollmentForm(request.POST)

        if form.is_valid():
            enrollment = form.save()

            messages.success(
                request,
                f"{enrollment.student.full_name} enrolled in "
                f"{enrollment.class_level.name} for "
                f"{enrollment.term.session.name} - "
                f"{enrollment.term.name}."
            )

            return redirect("enrollment_management")

    else:
        form = EnrollmentForm()

    enrollments = (
        Enrollment.objects
        .select_related(
            "student",
            "class_level",
            "term__session",
        )
        .order_by(
            "-term__session__name",
            "-term__id",
            "class_level__name",
            "student__surname",
            "student__first_name",
        )
    )

    sessions = AcademicSession.objects.order_by("-id")
    terms = Term.objects.select_related("session").order_by(
        "-session__id",
        "id",
    )
    classes = ClassLevel.objects.order_by("name")

    search = request.GET.get("search", "").strip()
    session_id = request.GET.get("session", "").strip()
    term_id = request.GET.get("term", "").strip()
    class_id = request.GET.get("class_level", "").strip()

    if search:
        enrollments = enrollments.filter(
            student__admission_number__icontains=search
        ) | enrollments.filter(
            student__surname__icontains=search
        ) | enrollments.filter(
            student__first_name__icontains=search
        ) | enrollments.filter(
            student__other_names__icontains=search
        )

    if session_id:
        enrollments = enrollments.filter(
            term__session_id=session_id
        )

    if term_id:
        enrollments = enrollments.filter(
            term_id=term_id
        )

    if class_id:
        enrollments = enrollments.filter(
            class_level_id=class_id
        )

    enrollments = enrollments.distinct()

    context = {
        "form": form,
        "enrollments": enrollments,
        "sessions": sessions,
        "terms": terms,
        "classes": classes,
        "search": search,
        "selected_session": session_id,
        "selected_term": term_id,
        "selected_class": class_id,
    }

    return render(
        request,
        "school/enrollment_management.html",
        context,
    )

def student_detail(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related("current_class"),
        id=student_id,
    )

    enrollments = student.enrollments.select_related(
        "class_level",
        "term__session",
    ).order_by(
        "-term__session__name",
        "-term__id",
    )

    return render(
        request,
        "school/student_detail.html",
        {
            "student": student,
            "enrollments": enrollments,
        },
    )


def student_edit(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)

        if form.is_valid():
            form.save()
            messages.success(request, "Student updated successfully.")
            return redirect("student_detail", student_id=student.id)
    else:
        form = StudentForm(instance=student)

    return render(
        request,
        "school/student_form.html",
        {
            "form": form,
            "title": "Edit Student",
            "student": student,
        },
    )


def teacher_list(request):
    teachers = Teacher.objects.all().order_by(
        "surname",
        "first_name",
    )

    return render(
        request,
        "school/teacher_list.html",
        {
            "teachers": teachers,
        },
    )


def teacher_add(request):
    if request.method == "POST":
        form = TeacherForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Teacher added successfully.")
            return redirect("teacher_list")
    else:
        form = TeacherForm()

    return render(
        request,
        "school/teacher_form.html",
        {
            "form": form,
            "title": "Add Teacher",
        },
    )


def teacher_edit(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)

        if form.is_valid():
            form.save()
            messages.success(request, "Teacher updated successfully.")
            return redirect("teacher_list")
    else:
        form = TeacherForm(instance=teacher)

    return render(
        request,
        "school/teacher_form.html",
        {
            "form": form,
            "title": "Edit Teacher",
            "teacher": teacher,
        },
    )



def teacher_account_manage(request, teacher_id):
    """
    Create or update the Django login account linked to a teacher.
    """

    if not request.user.is_authenticated:
        return redirect("admin:login")

    if not request.user.is_staff:
        messages.error(
            request,
            "You do not have permission to manage teacher accounts.",
        )
        return redirect("dashboard")

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    try:
        account = (
            TeacherAccount.objects
            .select_related("user")
            .get(teacher=teacher)
        )
    except TeacherAccount.DoesNotExist:
        account = None

    if request.method == "POST":
        username = request.POST.get(
            "username",
            "",
        ).strip()

        password = request.POST.get(
            "password",
            "",
        )

        confirm_password = request.POST.get(
            "confirm_password",
            "",
        )

        errors = []

        if not username:
            errors.append(
                "Username is required."
            )

        if password != confirm_password:
            errors.append(
                "The passwords do not match."
            )

        if account is None and not password:
            errors.append(
                "Password is required when creating a new account."
            )

        existing_user = (
            User.objects
            .filter(username=username)
            .exclude(
                pk=account.user.pk if account else None
            )
            .first()
        )

        if existing_user:
            errors.append(
                "That username is already being used."
            )

        if errors:
            for error in errors:
                messages.error(
                    request,
                    error,
                )

        else:
            if account is None:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                )

                account = TeacherAccount.objects.create(
                    teacher=teacher,
                    user=user,
                    active=True,
                )

                messages.success(
                    request,
                    f"Login account created successfully for "
                    f"{teacher.full_name}.",
                )

            else:
                user = account.user
                user.username = username

                if password:
                    user.set_password(password)

                user.save()

                if not account.active:
                    account.active = True
                    account.save(update_fields=["active"])

                messages.success(
                    request,
                    f"Login account updated successfully for "
                    f"{teacher.full_name}.",
                )

            return redirect(
                "teacher_list"
            )

    return render(
        request,
        "school/teacher_account_form.html",
        {
            "teacher": teacher,
            "account": account,
        },
    )

def subject_list(request):
    subjects = Subject.objects.all().order_by("name")

    return render(
        request,
        "school/subject_list.html",
        {
            "subjects": subjects,
        },
    )


def subject_add(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Subject added successfully.")
            return redirect("subject_list")
    else:
        form = SubjectForm()

    return render(
        request,
        "school/subject_form.html",
        {
            "form": form,
            "title": "Add Subject",
        },
    )


def subject_edit(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    if request.method == "POST":
        form = SubjectForm(request.POST, instance=subject)

        if form.is_valid():
            form.save()
            messages.success(request, "Subject updated successfully.")
            return redirect("subject_list")
    else:
        form = SubjectForm(instance=subject)

    return render(
        request,
        "school/subject_form.html",
        {
            "form": form,
            "title": "Edit Subject",
            "subject": subject,
        },
    )


def class_list(request):
    classes = list(
        ClassLevel.objects
        .select_related("form_teacher")
        .order_by("name")
    )

    active_teachers = list(
        Teacher.objects
        .filter(active=True)
        .order_by("surname", "first_name")
    )

    if request.method == "POST":
        teacher_map = {
            str(teacher.id): teacher
            for teacher in active_teachers
        }

        assignments = {}
        teacher_classes = {}
        valid = True

        for class_level in classes:
            teacher_id = request.POST.get(
                f"teacher_{class_level.id}",
                ""
            ).strip()

            if not teacher_id:
                assignments[class_level.id] = None
                continue

            teacher = teacher_map.get(teacher_id)

            if teacher is None:
                messages.error(
                    request,
                    f"Invalid teacher selected for {class_level.name}."
                )
                valid = False
                break

            # Check whether this teacher is already assigned
            # to another class in the database.
            existing_class = (
                ClassLevel.objects
                .filter(form_teacher=teacher)
                .exclude(pk=class_level.id)
                .first()
            )

            if existing_class:
                messages.error(
                    request,
                    f"{teacher.full_name} is already assigned as "
                    f"Form Teacher for {existing_class.name}."
                )
                valid = False
                break

            # Also prevent assigning the same teacher to two
            # different classes in this same bulk submission.
            if teacher.id in teacher_classes:
                previous_class = teacher_classes[teacher.id]

                messages.error(
                    request,
                    f"{teacher.full_name} cannot be assigned to both "
                    f"{previous_class} and {class_level.name}. "
                    f"One Form Teacher can only have one class."
                )
                valid = False
                break

            assignments[class_level.id] = teacher
            teacher_classes[teacher.id] = class_level.name

        if valid:
            for class_level in classes:
                class_level.form_teacher = assignments.get(
                    class_level.id
                )
                class_level.save(update_fields=["form_teacher"])

            messages.success(
                request,
                "Form Teacher assignments updated successfully."
            )

            return redirect("class_list")

    return render(
        request,
        "school/class_list.html",
        {
            "classes": classes,
            "active_teachers": active_teachers,
        },
    )



def teacher_form_class_manage(request, teacher_id):
    """
    Assign or change the Form Teacher class for a specific teacher.
    Uses the existing ClassTeacherForm validation so that one teacher
    cannot be assigned to more than one class.
    """

    if not request.user.is_authenticated:
        return redirect("admin:login")

    if not request.user.is_staff:
        messages.error(
            request,
            "You do not have permission to manage Form Teacher assignments.",
        )
        return redirect("dashboard")

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    current_class = (
        ClassLevel.objects
        .filter(form_teacher=teacher)
        .first()
    )

    classes = ClassLevel.objects.all().order_by("name")

    if request.method == "POST":

        selected_class_id = request.POST.get(
            "class_level",
            "",
        ).strip()

        # ----------------------------------------------------
        # REMOVE FORM TEACHER ASSIGNMENT
        # ----------------------------------------------------
        if selected_class_id == "":

            if current_class:
                current_class.form_teacher = None
                current_class.save(
                    update_fields=["form_teacher"]
                )

                messages.success(
                    request,
                    f"Form Teacher assignment removed from "
                    f"{current_class.name}.",
                )
            else:
                messages.info(
                    request,
                    f"{teacher.full_name} is not currently assigned "
                    f"as Form Teacher of any class.",
                )

            return redirect(
                "teacher_list"
            )

        # ----------------------------------------------------
        # SELECT CLASS
        # ----------------------------------------------------
        try:
            selected_class = ClassLevel.objects.get(
                id=selected_class_id
            )
        except (ClassLevel.DoesNotExist, ValueError):
            messages.error(
                request,
                "The selected class is invalid.",
            )
            return redirect(
                "teacher_form_class_manage",
                teacher_id=teacher.id,
            )

        # ----------------------------------------------------
        # CHECK WHETHER ANOTHER TEACHER OWNS THE CLASS
        # ----------------------------------------------------
        if (
            selected_class.form_teacher
            and selected_class.form_teacher_id != teacher.id
        ):
            messages.error(
                request,
                f"{selected_class.name} is already assigned to "
                f"{selected_class.form_teacher.full_name}.",
            )

            return redirect(
                "teacher_form_class_manage",
                teacher_id=teacher.id,
            )

        # ----------------------------------------------------
        # CHECK WHETHER THIS TEACHER ALREADY OWNS ANOTHER CLASS
        # ----------------------------------------------------
        another_class = (
            ClassLevel.objects
            .filter(form_teacher=teacher)
            .exclude(id=selected_class.id)
            .first()
        )

        if another_class:
            messages.error(
                request,
                f"{teacher.full_name} is already assigned as "
                f"Form Teacher for {another_class.name}. "
                f"Remove that assignment first.",
            )

            return redirect(
                "teacher_form_class_manage",
                teacher_id=teacher.id,
            )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------
        selected_class.form_teacher = teacher
        selected_class.save(
            update_fields=["form_teacher"]
        )

        messages.success(
            request,
            f"{teacher.full_name} is now Form Teacher for "
            f"{selected_class.name}.",
        )

        return redirect(
            "teacher_list"
        )

    return render(
        request,
        "school/teacher_form_class.html",
        {
            "teacher": teacher,
            "current_class": current_class,
            "classes": classes,
        },
    )

def class_teacher_edit(request, class_id):
    class_level = get_object_or_404(ClassLevel, id=class_id)

    if request.method == "POST":
        form = ClassTeacherForm(request.POST, instance=class_level)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Form teacher for {class_level.name} updated successfully.",
            )
            return redirect("class_list")
    else:
        form = ClassTeacherForm(instance=class_level)

    return render(
        request,
        "school/class_teacher_form.html",
        {
            "form": form,
            "class_level": class_level,
        },
    )


def score_entry(request):
    current_term = Term.objects.filter(is_current=True).first()

    classes = ClassLevel.objects.all().order_by("name")
    subjects = Subject.objects.filter(active=True).order_by("name")

    selected_class = None
    selected_subject = None
    enrollments = []
    score_data = {}

    class_id = request.POST.get("class_id") or request.GET.get("class_id")
    subject_id = request.POST.get("subject_id") or request.GET.get("subject_id")

    if class_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id)
        except (ClassLevel.DoesNotExist, ValueError):
            selected_class = None

    if subject_id:
        try:
            selected_subject = Subject.objects.get(
                id=subject_id,
                active=True,
            )
        except (Subject.DoesNotExist, ValueError):
            selected_subject = None

    if current_term and selected_class and selected_subject:
        enrollments = (
            Enrollment.objects
            .filter(
                term=current_term,
                class_level=selected_class,
                student__active=True,
            )
            .select_related("student")
            .order_by(
                "student__surname",
                "student__first_name",
            )
        )

        existing_scores = Score.objects.filter(
            enrollment__in=enrollments,
            subject=selected_subject,
        )

        score_data = {
            score.enrollment_id: score
            for score in existing_scores
        }

    if request.method == "POST" and enrollments and selected_subject:
        errors = []

        for enrollment in enrollments:
            prefix = f"student_{enrollment.id}"

            ca1_raw = request.POST.get(
                f"{prefix}_ca1",
                "",
            ).strip()

            ca2_raw = request.POST.get(
                f"{prefix}_ca2",
                "",
            ).strip()

            ca3_raw = request.POST.get(
                f"{prefix}_ca3",
                "",
            ).strip()

            exam_raw = request.POST.get(
                f"{prefix}_exam",
                "",
            ).strip()

            values = {
                "CA 1": ca1_raw,
                "CA 2": ca2_raw,
                "CA 3": ca3_raw,
                "Exam": exam_raw,
            }

            cleaned = {}
            row_has_error = False

            for label, raw_value in values.items():
                if raw_value == "":
                    cleaned[label] = Decimal("0")
                    continue

                try:
                    value = Decimal(raw_value)
                except InvalidOperation:
                    errors.append(
                        f"{enrollment.student.full_name}: "
                        f"{label} is not a valid number."
                    )
                    row_has_error = True
                    continue

                cleaned[label] = value

            if row_has_error:
                continue

            ca1 = cleaned.get("CA 1", Decimal("0"))
            ca2 = cleaned.get("CA 2", Decimal("0"))
            ca3 = cleaned.get("CA 3", Decimal("0"))
            exam = cleaned.get("Exam", Decimal("0"))

            if ca1 < 0 or ca1 > 10:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "CA 1 must be between 0 and 10."
                )
                continue

            if ca2 < 0 or ca2 > 10:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "CA 2 must be between 0 and 10."
                )
                continue

            if ca3 < 0 or ca3 > 10:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "CA 3 must be between 0 and 10."
                )
                continue

            if exam < 0 or exam > 70:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "Exam must be between 0 and 70."
                )
                continue

            Score.objects.update_or_create(
                enrollment=enrollment,
                subject=selected_subject,
                defaults={
                    "ca1_score": ca1,
                    "ca2_score": ca2,
                    "ca3_score": ca3,
                    "exam_score": exam,
                },
            )

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(
                request,
                f"Scores for {selected_subject.name} — "
                f"{selected_class.name} saved successfully.",
            )

            return redirect(
                f"/scores/?class_id={selected_class.id}"
                f"&subject_id={selected_subject.id}"
            )

        existing_scores = Score.objects.filter(
            enrollment__in=enrollments,
            subject=selected_subject,
        )

        score_data = {
            score.enrollment_id: score
            for score in existing_scores
        }

    context = {
        "current_term": current_term,
        "classes": classes,
        "subjects": subjects,
        "selected_class": selected_class,
        "selected_subject": selected_subject,
        "enrollments": enrollments,
        "score_data": score_data,
    }

    return render(
        request,
        "school/score_entry.html",
        context,
    )


def teacher_login(request):
    if request.user.is_authenticated:
        return redirect("teacher_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            try:
                account = user.teacher_account
            except TeacherAccount.DoesNotExist:
                account = None

            if account and account.active and account.teacher.active:
                login(request, user)
                return redirect("teacher_dashboard")

            messages.error(
                request,
                "This account is not linked to an active teacher account.",
            )
        else:
            messages.error(
                request,
                "Invalid username or password.",
            )

    return render(
        request,
        "school/teacher_login.html",
    )


@login_required(login_url="/teacher-login/")
@login_required(login_url="/teacher-login/")
def teacher_add_student(request):
    """Allow a Form Teacher to add a student only to their assigned class."""

    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        messages.error(
            request,
            "Your user account is not linked to a teacher account.",
        )
        logout(request)
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        logout(request)
        messages.error(
            request,
            "Your teacher account is inactive.",
        )
        return redirect("teacher_login")

    form_teacher_classes = list(
        ClassLevel.objects
        .filter(form_teacher=account.teacher)
        .order_by("name")
    )

    if not form_teacher_classes:
        messages.error(
            request,
            "You are not currently assigned as a Form Teacher to any class.",
        )
        return redirect("teacher_dashboard")

    if len(form_teacher_classes) > 1:
        messages.error(
            request,
            "Your account is assigned to more than one Form Teacher class. "
            "Please contact the administrator.",
        )
        return redirect("teacher_dashboard")

    assigned_class = form_teacher_classes[0]

    current_term = (
        Term.objects
        .filter(is_current=True)
        .select_related("session")
        .order_by("-session_id", "-id")
        .first()
    )

    if current_term is None:
        messages.error(
            request,
            "No current academic term has been configured.",
        )
        return redirect("teacher_dashboard")

    # Automatically generate the next admission number.
    # Existing admission numbers are left unchanged.
    admission_numbers = Student.objects.values_list(
        "admission_number",
        flat=True,
    )

    highest_number = 0

    for admission_number in admission_numbers:
        value = str(admission_number).strip()

        if value.upper().startswith("RFC"):
            suffix = value[3:]

            if suffix.isdigit():
                highest_number = max(
                    highest_number,
                    int(suffix),
                )

    generated_admission_number = f"RFC{highest_number + 1:03d}"

    if request.method == "POST":
        form = StudentForm(request.POST)

        # Admission number is generated by the server.
        # It must not be required from the teacher.
        form.fields["admission_number"].required = False
        form.fields["admission_number"].disabled = True
        form.fields["admission_number"].initial = generated_admission_number

        # Never trust a class or admission number submitted by the browser.
        form.instance.current_class = assigned_class
        form.instance.admission_number = generated_admission_number

        if form.is_valid():
            student = form.save(commit=False)
            student.current_class = assigned_class
            student.active = True
            student.save()

            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                term=current_term,
                defaults={
                    "class_level": assigned_class,
                },
            )

            if not created and enrollment.class_level_id != assigned_class.id:
                enrollment.class_level = assigned_class
                enrollment.save(update_fields=["class_level"])

            messages.success(
                request,
                f"{student.full_name} was added to "
                f"{assigned_class.name} for {current_term}.",
            )
            return redirect("teacher_dashboard")
    else:
        form = StudentForm()

    # Teachers must not enter or alter the admission number.
    # It is generated automatically by the server.
    form.fields["admission_number"].required = False
    form.fields["admission_number"].disabled = True
    form.fields["admission_number"].initial = generated_admission_number

    # Teachers must not select or alter the class.
    form.fields["current_class"].disabled = True
    form.fields["current_class"].initial = assigned_class

    # Teachers cannot activate/deactivate students.
    form.fields["active"].disabled = True
    form.fields["active"].initial = True

    return render(
        request,
        "school/teacher_student_form.html",
        {
            "form": form,
            "teacher": account.teacher,
            "assigned_class": assigned_class,
            "current_term": current_term,
            "generated_admission_number": generated_admission_number,
        },
    )


def teacher_dashboard(request):
    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        messages.error(
            request,
            "Your user account is not linked to a teacher account.",
        )
        logout(request)
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        logout(request)
        messages.error(
            request,
            "Your teacher account is inactive.",
        )
        return redirect("teacher_login")

    form_teacher_classes = (
        ClassLevel.objects
        .filter(form_teacher=account.teacher)
        .order_by("name")
    )

    class_status = []

    for class_level in form_teacher_classes:

        enrollments = list(
            Enrollment.objects
            .filter(class_level=class_level)
            .select_related("student", "term")
        )

        active_subject_count = ClassSubject.objects.filter(
            class_level=class_level,
            active=True,
        ).count()

        students_with_scores = 0
        students_submitted = 0
        students_approved = 0
        students_pending = 0
        students_with_comments = 0

        for enrollment in enrollments:

            scores = list(
                Score.objects
                .filter(enrollment=enrollment)
            )

            score_count = len(scores)
            submitted_count = sum(
                1 for score in scores
                if score.submitted
            )
            approved_count = sum(
                1 for score in scores
                if score.approved
            )

            if (
                active_subject_count > 0
                and score_count >= active_subject_count
            ):
                students_with_scores += 1

            if (
                active_subject_count > 0
                and submitted_count >= active_subject_count
            ):
                students_submitted += 1

            if (
                active_subject_count > 0
                and approved_count >= active_subject_count
            ):
                students_approved += 1

            if (
                submitted_count > 0
                and submitted_count > approved_count
            ):
                students_pending += 1

            if (
                enrollment.form_teacher_comment
                and enrollment.academic_performance_comment
            ):
                students_with_comments += 1

        students = [
            {
                "id": enrollment.student.id,
                "full_name": " ".join(
                    part
                    for part in [
                        enrollment.student.surname,
                        enrollment.student.first_name,
                        enrollment.student.other_names,
                    ]
                    if part
                ),
                "admission_number": enrollment.student.admission_number,
                "gender": enrollment.student.gender,
                "date_of_birth": enrollment.student.date_of_birth,
                "date_admitted": enrollment.student.date_admitted,
                "phone_number": enrollment.student.phone_number,
                "email": enrollment.student.email,
            }
            for enrollment in enrollments
            if enrollment.student.active
        ]

        class_status.append(
            {
                "class_level": class_level,
                "student_count": len(enrollments),
                "students_with_scores": students_with_scores,
                "students_submitted": students_submitted,
                "students_approved": students_approved,
                "students_pending": students_pending,
                "students_with_comments": students_with_comments,
                "subject_count": active_subject_count,
                "students": students,
            }
        )

    return render(
        request,
        "school/teacher_dashboard.html",
        {
            "teacher": account.teacher,
            "class_status": class_status,
        },
    )

def teacher_logout(request):
    logout(request)
    return redirect("teacher_login")


@login_required(login_url="/teacher-login/")
def teacher_score_entry(request, assignment_id):
    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        logout(request)
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        logout(request)
        return redirect("teacher_login")

    assignment = get_object_or_404(
        TeachingAssignment.objects.select_related(
            "teacher",
            "class_level",
            "subject",
        ),
        id=assignment_id,
        teacher=account.teacher,
        active=True,
    )

    current_term = Term.objects.filter(is_current=True).first()

    enrollments = []
    score_data = {}

    if current_term:
        enrollments = (
            Enrollment.objects
            .filter(
                term=current_term,
                class_level=assignment.class_level,
                student__active=True,
            )
            .select_related("student")
            .order_by(
                "student__surname",
                "student__first_name",
            )
        )

        existing_scores = Score.objects.filter(
            enrollment__in=enrollments,
            subject=assignment.subject,
        )

        score_data = {
            score.enrollment_id: score
            for score in existing_scores
        }

    # ---------------------------------------------------------
    # SUBMIT SCORES FOR APPROVAL
    # ---------------------------------------------------------
    if request.method == "POST" and request.POST.get("action") == "submit":

        scores = Score.objects.filter(
            enrollment__in=enrollments,
            subject=assignment.subject,
        )

        if not scores.exists():
            messages.error(
                request,
                "There are no scores to submit."
            )
        else:
            scores.update(
                submitted=True,
                approved=False,
            )

            messages.success(
                request,
                "Scores submitted successfully for admin approval."
            )

        return redirect(
            "teacher_score_entry",
            assignment_id=assignment.id,
        )

    # ---------------------------------------------------------
    # SAVE SCORES
    # ---------------------------------------------------------
    if request.method == "POST" and request.POST.get("action") == "save":

        errors = []

        for enrollment in enrollments:

            existing_score = Score.objects.filter(
                enrollment=enrollment,
                subject=assignment.subject,
            ).first()

            # Submitted and approved scores are locked.
            # Only scores returned by the administrator can be edited.
            if existing_score and (
                existing_score.submitted
                or existing_score.approved
            ):
                continue

            prefix = f"student_{enrollment.id}"

            ca1_raw = request.POST.get(
                f"{prefix}_ca1",
                "",
            ).strip()

            ca2_raw = request.POST.get(
                f"{prefix}_ca2",
                "",
            ).strip()

            ca3_raw = request.POST.get(
                f"{prefix}_ca3",
                "",
            ).strip()

            exam_raw = request.POST.get(
                f"{prefix}_exam",
                "",
            ).strip()

            try:
                ca1 = Decimal(ca1_raw or "0")
                ca2 = Decimal(ca2_raw or "0")
                ca3 = Decimal(ca3_raw or "0")
                exam = Decimal(exam_raw or "0")

            except InvalidOperation:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "one or more scores are invalid."
                )
                continue

            if not 0 <= ca1 <= 10:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "CA1 must be 0–10."
                )
                continue

            if not 0 <= ca2 <= 10:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "CA2 must be 0–10."
                )
                continue

            if not 0 <= ca3 <= 10:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "CA3 must be 0–10."
                )
                continue

            if not 0 <= exam <= 70:
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "Exam must be 0–70."
                )
                continue

            Score.objects.update_or_create(
                enrollment=enrollment,
                subject=assignment.subject,
                defaults={
                    "ca1_score": ca1,
                    "ca2_score": ca2,
                    "ca3_score": ca3,
                    "exam_score": exam,
                    "submitted": False,
                    "approved": False,
                },
            )

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(
                request,
                "Scores saved successfully as a draft."
            )

        return redirect(
            "teacher_score_entry",
            assignment_id=assignment.id,
        )

    # Refresh scores after POST.
    if current_term:
        existing_scores = Score.objects.filter(
            enrollment__in=enrollments,
            subject=assignment.subject,
        )

        score_data = {
            score.enrollment_id: score
            for score in existing_scores
        }

    has_scores = any(
        score is not None
        for score in score_data.values()
    )

    all_submitted = (
        bool(enrollments)
        and all(
            score_data.get(enrollment.id)
            and score_data[enrollment.id].submitted
            for enrollment in enrollments
        )
    )

    all_approved = (
        bool(enrollments)
        and all(
            score_data.get(enrollment.id)
            and score_data[enrollment.id].approved
            for enrollment in enrollments
        )
    )

    return render(
        request,
        "school/teacher_score_entry.html",
        {
            "teacher": account.teacher,
            "assignment": assignment,
            "current_term": current_term,
            "enrollments": enrollments,
            "score_data": score_data,
            "has_scores": has_scores,
            "all_submitted": all_submitted,
            "all_approved": all_approved,
        },
    )


# ============================================================
# FORM TEACHER — FULL CLASS SCORE ENTRY
# ============================================================

@login_required(login_url="/teacher-login/")
def form_teacher_score_entry(request, class_id):

    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        logout(request)
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        logout(request)
        return redirect("teacher_login")

    class_level = get_object_or_404(
        ClassLevel.objects.select_related("form_teacher"),
        id=class_id,
    )

    # Only the officially assigned Form Teacher may enter
    # scores for the entire class.
    if class_level.form_teacher_id != account.teacher.id:
        messages.error(
            request,
            "You are not the Form Teacher assigned to this class.",
        )
        return redirect("teacher_dashboard")

    current_term = Term.objects.filter(
        is_current=True
    ).first()

    if current_term is None:
        messages.error(
            request,
            "There is no current academic term.",
        )
        return redirect("teacher_dashboard")

    enrollments = list(
        Enrollment.objects
        .filter(
            class_level=class_level,
            term=current_term,
            student__active=True,
        )
        .select_related("student")
        .order_by(
            "student__surname",
            "student__first_name",
        )
    )

    subjects = list(
        Subject.objects
        .filter(active=True)
        .order_by("name")
    )

    existing_scores = Score.objects.filter(
        enrollment__in=enrollments,
        subject__in=subjects,
    )

    score_data = {
        (score.enrollment_id, score.subject_id): score
        for score in existing_scores
    }

    # Template-friendly nested score structure.
    score_matrix = {}

    for score in existing_scores:
        score_matrix.setdefault(
            score.enrollment_id,
            {}
        )[score.subject_id] = score

    # ------------------------------------------------------------
    # SUBMIT ALL CLASS SCORES
    # ------------------------------------------------------------

    if (
        request.method == "POST"
        and request.POST.get("action") == "submit"
    ):

        missing_scores = []

        for enrollment in enrollments:

            for subject in subjects:

                score = score_data.get(
                    (enrollment.id, subject.id)
                )

                if score is None:
                    missing_scores.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}"
                    )
                    continue

                if (
                    score.ca1_score is None
                    or score.ca2_score is None
                    or score.ca3_score is None
                    or score.exam_score is None
                ):
                    missing_scores.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}"
                    )

        if missing_scores:

            messages.error(
                request,
                "Submission blocked. The following student/subject "
                "scores are incomplete: "
                + "; ".join(missing_scores),
            )

        else:

            Score.objects.filter(
                enrollment__in=enrollments,
                subject__in=subjects,
                approved=False,
            ).update(
                submitted=True,
                approved=False,
            )

            messages.success(
                request,
                "All class scores have been submitted successfully "
                "for Admin approval.",
            )

        return redirect(
            "form_teacher_score_entry",
            class_id=class_level.id,
        )

    # ------------------------------------------------------------
    # SAVE ALL CLASS SCORES AS DRAFTS
    # ------------------------------------------------------------

    if (
        request.method == "POST"
        and request.POST.get("action") == "save"
    ):

        errors = []

        for enrollment in enrollments:

            for subject in subjects:

                existing_score = score_data.get(
                    (enrollment.id, subject.id)
                )

                # Submitted or approved scores are locked.
                if existing_score and (
                    existing_score.submitted
                    or existing_score.approved
                ):
                    continue

                prefix = (
                    f"student_{enrollment.id}_subject_{subject.id}"
                )

                ca1_raw = request.POST.get(
                    f"{prefix}_ca1",
                    "",
                ).strip()

                ca2_raw = request.POST.get(
                    f"{prefix}_ca2",
                    "",
                ).strip()

                ca3_raw = request.POST.get(
                    f"{prefix}_ca3",
                    "",
                ).strip()

                exam_raw = request.POST.get(
                    f"{prefix}_exam",
                    "",
                ).strip()

                try:
                    ca1 = Decimal(ca1_raw) if ca1_raw else None
                    ca2 = Decimal(ca2_raw) if ca2_raw else None
                    ca3 = Decimal(ca3_raw) if ca3_raw else None
                    exam = Decimal(exam_raw) if exam_raw else None

                except InvalidOperation:

                    errors.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}: invalid score."
                    )

                    continue

                if ca1 is not None and not 0 <= ca1 <= 10:
                    errors.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}: CA1 must be 0–10."
                    )
                    continue

                if ca2 is not None and not 0 <= ca2 <= 10:
                    errors.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}: CA2 must be 0–10."
                    )
                    continue

                if ca3 is not None and not 0 <= ca3 <= 10:
                    errors.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}: CA3 must be 0–10."
                    )
                    continue

                if exam is not None and not 0 <= exam <= 70:
                    errors.append(
                        f"{enrollment.student.full_name} — "
                        f"{subject.name}: Exam must be 0–70."
                    )
                    continue

                # If every field is blank and no existing score exists,
                # don't create an empty Score record.
                if (
                    ca1 is None
                    and ca2 is None
                    and ca3 is None
                    and exam is None
                ):

                    continue

                Score.objects.update_or_create(
                    enrollment=enrollment,
                    subject=subject,
                    defaults={
                        "ca1_score": ca1,
                        "ca2_score": ca2,
                        "ca3_score": ca3,
                        "exam_score": exam,
                        "submitted": False,
                        "approved": False,
                    },
                )

        if errors:

            for error in errors:
                messages.error(request, error)

        else:

            messages.success(
                request,
                "Class scores saved successfully as drafts.",
            )

        return redirect(
            "form_teacher_score_entry",
            class_id=class_level.id,
        )

    # Refresh score data after any request.
    existing_scores = Score.objects.filter(
        enrollment__in=enrollments,
        subject__in=subjects,
    )

    score_data = {
        (score.enrollment_id, score.subject_id): score
        for score in existing_scores
    }

    score_matrix = {}

    for score in existing_scores:
        score_matrix.setdefault(
            score.enrollment_id,
            {}
        )[score.subject_id] = score

    all_scores_exist = (
        bool(enrollments)
        and bool(subjects)
        and all(
            (enrollment.id, subject.id) in score_data
            for enrollment in enrollments
            for subject in subjects
        )
    )

    all_scores_complete = (
        all_scores_exist
        and all(
            score_data[
                (enrollment.id, subject.id)
            ].ca1_score is not None
            and score_data[
                (enrollment.id, subject.id)
            ].ca2_score is not None
            and score_data[
                (enrollment.id, subject.id)
            ].ca3_score is not None
            and score_data[
                (enrollment.id, subject.id)
            ].exam_score is not None
            for enrollment in enrollments
            for subject in subjects
        )
    )

    all_submitted = (
        all_scores_complete
        and all(
            score_data[
                (enrollment.id, subject.id)
            ].submitted
            for enrollment in enrollments
            for subject in subjects
        )
    )

    all_approved = (
        all_scores_complete
        and all(
            score_data[
                (enrollment.id, subject.id)
            ].approved
            for enrollment in enrollments
            for subject in subjects
        )
    )

    has_scores = bool(score_data)


    # ---------------------------------------------------------
    # STUDENT SCORE STATUS
    # ---------------------------------------------------------
    # IMPORTANT:
    # Status is calculated ONLY from subjects assigned to this
    # class through ClassSubject. This prevents subjects belonging
    # to another class/arm from affecting the student's status.
    # ---------------------------------------------------------

    class_subjects = list(
        ClassSubject.objects.filter(
            class_level=class_level,
            active=True,
            subject__active=True,
        ).select_related("subject").order_by("subject__name")
    )

    class_subject_ids = {
        cs.subject_id
        for cs in class_subjects
    }

    student_score_statuses = []

    for enrollment in enrollments:
        student_scores = [
            score
            for score in existing_scores
            if score.enrollment_id == enrollment.id
            and score.subject_id in class_subject_ids
        ]

        total_subjects = len(class_subject_ids)

        if total_subjects == 0:
            status = "No Subjects Assigned"
            status_class = "not-started"

        elif not student_scores:
            status = "Not Started"
            status_class = "not-started"

        else:
            score_by_subject = {
                score.subject_id: score
                for score in student_scores
            }

            complete_scores = [
                score
                for subject_id, score in score_by_subject.items()
                if (
                    score.ca1_score is not None
                    and score.ca2_score is not None
                    and score.ca3_score is not None
                    and score.exam_score is not None
                )
            ]

            complete_count = len(complete_scores)

            approved_count = sum(
                1
                for score in complete_scores
                if getattr(score, "approved", False)
            )

            submitted_count = sum(
                1
                for score in complete_scores
                if getattr(score, "submitted", False)
            )

            if (
                complete_count == total_subjects
                and approved_count == total_subjects
            ):
                status = "Approved"
                status_class = "approved"

            elif (
                complete_count == total_subjects
                and submitted_count == total_subjects
            ):
                status = "Submitted — Awaiting Approval"
                status_class = "submitted"

            elif submitted_count > 0:
                status = "Partially Submitted"
                status_class = "partial"

            elif complete_count > 0:
                status = "Draft Saved"
                status_class = "draft"

            else:
                status = "Not Started"
                status_class = "not-started"

        student_score_statuses.append({
            "enrollment": enrollment,
            "student": enrollment.student,
            "status": status,
            "status_class": status_class,
        })

    return render(
        request,
        "school/form_teacher_score_entry.html",
        {
            "student_score_statuses": student_score_statuses,
            "teacher": account.teacher,
            "class_level": class_level,
            "current_term": current_term,
            "enrollments": enrollments,
            "subjects": subjects,
            "score_data": score_data,
            "score_matrix": score_matrix,
            "has_scores": has_scores,
            "all_scores_exist": all_scores_exist,
            "all_scores_complete": all_scores_complete,
            "all_submitted": all_submitted,
            "all_approved": all_approved,
        },
    )


# ============================================================
# FORM TEACHER BEHAVIOUR COMMENTS
# ============================================================

def get_current_term():
    """
    Return the currently active academic term.
    """
    return (
        Term.objects
        .filter(is_current=True)
        .select_related("session")
        .order_by("-id")
        .first()
    )


def form_teacher_student_scores(request, class_id, student_id):
    """
    Form Teacher score entry for ONE student.

    Only subjects assigned to the student's class through
    ClassSubject are displayed.
    """

    from decimal import Decimal, InvalidOperation

    # -----------------------------------------------------
    # TEACHER ACCOUNT
    # -----------------------------------------------------

    account = None

    for key in [
        "teacher_account_id",
        "teacher_id",
        "teacher_account",
    ]:
        value = request.session.get(key)

        if value:
            try:
                account = TeacherAccount.objects.select_related(
                    "teacher"
                ).get(id=value)
                break
            except (
                TeacherAccount.DoesNotExist,
                ValueError,
                TypeError,
            ):
                pass

    if account is None and request.user.is_authenticated:
        try:
            account = TeacherAccount.objects.select_related(
                "teacher"
            ).get(user=request.user)
        except (
            TeacherAccount.DoesNotExist,
            AttributeError,
        ):
            pass

    if account is None:
        messages.error(
            request,
            "Please log in as a Form Teacher."
        )
        return redirect("teacher_login")

    # -----------------------------------------------------
    # CLASS SECURITY
    # -----------------------------------------------------

    class_level = get_object_or_404(
        ClassLevel.objects.select_related("form_teacher"),
        id=class_id,
    )

    if class_level.form_teacher_id != account.teacher_id:
        messages.error(
            request,
            "You are not the Form Teacher assigned to this class."
        )
        return redirect("teacher_dashboard")

    # -----------------------------------------------------
    # CURRENT TERM
    # -----------------------------------------------------

    term = get_current_term()

    if term is None:
        messages.error(
            request,
            "There is no current academic term configured."
        )
        return redirect("teacher_dashboard")

    # -----------------------------------------------------
    # STUDENT MUST BELONG TO THIS CLASS AND TERM
    # -----------------------------------------------------

    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            "student",
            "class_level",
            "term",
        ),
        student_id=student_id,
        class_level=class_level,
        term=term,
    )

    student = enrollment.student

    # =====================================================
    # CRITICAL SUBJECT FILTER
    #
    # ONLY ClassSubject records belonging to this class.
    # =====================================================

    class_subjects = list(
        ClassSubject.objects
        .filter(
            class_level_id=class_level.id,
            active=True,
            subject__active=True,
        )
        .select_related("subject")
        .order_by("subject__name")
    )

    subjects = [
        class_subject.subject
        for class_subject in class_subjects
    ]

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        action = request.POST.get("action", "save")

        for subject in subjects:

            score = (
                Score.objects
                .filter(
                    enrollment=enrollment,
                    subject=subject,
                )
                .first()
            )

            # Approved scores cannot be changed.
            if score and score.approved:
                continue

            # Submitted scores cannot be changed until
            # Admin returns them.
            if score and score.submitted:
                continue

            def get_value(field):

                raw = request.POST.get(
                    f"{field}_{subject.id}",
                    ""
                ).strip()

                if raw == "":
                    return None

                try:
                    return Decimal(raw)
                except (
                    InvalidOperation,
                    ValueError,
                ):
                    raise ValueError(
                        f"Invalid {field.upper()} score "
                        f"for {subject.name}."
                    )

            try:
                ca1 = get_value("ca1")
                ca2 = get_value("ca2")
                ca3 = get_value("ca3")
                exam = get_value("exam")

            except ValueError as error:

                messages.error(
                    request,
                    str(error)
                )

                return redirect(
                    "form_teacher_student_scores",
                    class_id=class_id,
                    student_id=student_id,
                )

            # -------------------------------------------------
            # RANGE CHECK
            # -------------------------------------------------

            limits = [
                ("CA1", ca1, Decimal("10")),
                ("CA2", ca2, Decimal("10")),
                ("CA3", ca3, Decimal("10")),
                ("Exam", exam, Decimal("70")),
            ]

            for label, value, maximum in limits:

                if value is not None:

                    if value < Decimal("0") or value > maximum:

                        messages.error(
                            request,
                            f"{subject.name}: {label} must be "
                            f"between 0 and {maximum}."
                        )

                        return redirect(
                            "form_teacher_student_scores",
                            class_id=class_id,
                            student_id=student_id,
                        )

            # -------------------------------------------------
            # EMPTY SUBJECT
            # -------------------------------------------------

            if (
                ca1 is None
                and ca2 is None
                and ca3 is None
                and exam is None
            ):

                if score and not score.submitted and not score.approved:
                    score.delete()

                continue

            # -------------------------------------------------
            # SAVE DRAFT
            # -------------------------------------------------

            if score is None:

                score = Score(
                    enrollment=enrollment,
                    subject=subject,
                )

            score.ca1_score = ca1
            score.ca2_score = ca2
            score.ca3_score = ca3
            score.exam_score = exam

            score.submitted = False
            score.approved = False

            score.save()

        # =====================================================
        # SUBMIT ALL STUDENT SCORES
        # =====================================================

        if action == "submit":

            scores = {
                score.subject_id: score
                for score in Score.objects.filter(
                    enrollment=enrollment,
                    subject__in=subjects,
                )
            }

            incomplete = []

            for subject in subjects:

                score = scores.get(subject.id)

                if score is None:

                    incomplete.append(subject.name)
                    continue

                # Approved scores are already valid.
                if score.approved:
                    continue

                if (
                    score.ca1_score is None
                    or score.ca2_score is None
                    or score.ca3_score is None
                    or score.exam_score is None
                ):

                    incomplete.append(subject.name)

            if incomplete:

                messages.error(
                    request,
                    "Complete all scores before submitting: "
                    + ", ".join(incomplete)
                )

            else:

                for subject in subjects:

                    score = scores.get(subject.id)

                    if score is None:
                        continue

                    if score.approved:
                        continue

                    score.submitted = True
                    score.approved = False

                    score.save(
                        update_fields=[
                            "submitted",
                            "approved",
                        ]
                    )

                messages.success(
                    request,
                    f"Scores for {student.full_name} "
                    "have been submitted for Admin approval."
                )

        else:

            messages.success(
                request,
                f"Draft scores saved for {student.full_name}."
            )

        return redirect(
            "form_teacher_student_scores",
            class_id=class_id,
            student_id=student_id,
        )

    # =====================================================
    # DISPLAY DATA
    # =====================================================

    score_matrix = {}

    for subject in subjects:

        score_matrix[subject.id] = (
            Score.objects
            .filter(
                enrollment=enrollment,
                subject=subject,
            )
            .first()
        )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    all_scores_complete = True
    all_submitted = True
    all_approved = True

    for subject in subjects:

        score = score_matrix.get(subject.id)

        if score is None:

            all_scores_complete = False
            all_submitted = False
            all_approved = False

            continue

        if (
            score.ca1_score is None
            or score.ca2_score is None
            or score.ca3_score is None
            or score.exam_score is None
        ):

            all_scores_complete = False

        if not score.submitted:
            all_submitted = False

        if not score.approved:
            all_approved = False

    return render(
        request,
        "school/form_teacher_student_scores.html",
        {
            "class_level": class_level,
            "term": term,
            "student": student,
            "enrollment": enrollment,

            # ONLY subjects assigned to this class.
            "subjects": subjects,
            "class_subjects": class_subjects,

            "score_matrix": score_matrix,

            "all_scores_complete": all_scores_complete,
            "all_submitted": all_submitted,
            "all_approved": all_approved,
        },
    )



def form_teacher_student_comments(request, class_id, student_id):
    """
    Form Teacher comments for ONE student.

    Only the Form Teacher assigned to the class may manage the student's
    behaviour and principal's overall comments.
    """
    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        logout(request)
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        logout(request)
        return redirect("teacher_login")

    class_level = get_object_or_404(
        ClassLevel.objects.select_related("form_teacher"),
        id=class_id,
    )

    # Only the officially assigned Form Teacher may manage comments.
    if class_level.form_teacher_id != account.teacher.id:
        messages.error(
            request,
            "You are not the Form Teacher assigned to this class.",
        )
        return redirect("teacher_dashboard")

    current_term = Term.objects.filter(is_current=True).first()

    if current_term is None:
        messages.error(
            request,
            "There is no current academic term.",
        )
        return redirect("teacher_dashboard")

    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            "student",
            "class_level",
            "term",
        ),
        student_id=student_id,
        class_level=class_level,
        term=current_term,
        student__active=True,
    )

    student = enrollment.student

    # ------------------------------------------------------------
    # CALCULATE THE STUDENT'S OVERALL ACADEMIC GRADE
    # ------------------------------------------------------------

    approved_scores = (
        Score.objects
        .filter(
            enrollment=enrollment,
            approved=True,
        )
        .select_related("subject")
    )

    totals = []

    for score in approved_scores:
        totals.append(score.total)

    academic_grade = ""

    if totals:
        average = sum(totals) / len(totals)

        grade_record = (
            GradeScale.objects
            .filter(
                minimum_score__lte=average,
                maximum_score__gte=average,
            )
            .first()
        )

        if grade_record:
            academic_grade = grade_record.grade

    if request.method == "POST":
        valid_behaviour_values = dict(
            Enrollment.FORM_TEACHER_COMMENT_CHOICES
        )

        valid_academic_values = dict(
            Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
        )

        behaviour_comment = request.POST.get(
            "behaviour_comment",
            "",
        ).strip()

        academic_comment = request.POST.get(
            "academic_comment",
            "",
        ).strip()

        errors = []

        if (
            behaviour_comment
            and behaviour_comment not in valid_behaviour_values
        ):
            errors.append("Invalid behaviour comment.")

        if (
            academic_comment
            and academic_comment not in valid_academic_values
        ):
            errors.append(
                "Invalid principal's overall comment."
            )

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            enrollment.form_teacher_comment = behaviour_comment
            enrollment.academic_performance_comment = academic_comment

            enrollment.save(
                update_fields=[
                    "form_teacher_comment",
                    "academic_performance_comment",
                ]
            )

            messages.success(
                request,
                "Form Teacher comments saved successfully.",
            )

            return redirect(
                "form_teacher_student_comments",
                class_id=class_level.id,
                student_id=student.id,
            )

    return render(
        request,
        "school/form_teacher_student_comments.html",
        {
            "teacher": account.teacher,
            "class_level": class_level,
            "current_term": current_term,
            "enrollment": enrollment,
            "student": student,
            "academic_grade": academic_grade,
            "comment_choices": (
                Enrollment.FORM_TEACHER_COMMENT_CHOICES
            ),
            "academic_comment_choices": (
                Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
            ),
        },
    )

def form_teacher_comments(request, class_id):
    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        logout(request)
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        logout(request)
        return redirect("teacher_login")

    class_level = get_object_or_404(
        ClassLevel.objects.select_related("form_teacher"),
        id=class_id,
    )

    # Only the teacher officially assigned as Form Teacher
    # may manage the behaviour comments for this class.
    if class_level.form_teacher_id != account.teacher.id:
        messages.error(
            request,
            "You are not the Form Teacher assigned to this class.",
        )
        return redirect("teacher_dashboard")

    current_term = Term.objects.filter(is_current=True).first()

    if current_term is None:
        messages.error(
            request,
            "There is no current academic term.",
        )
        return redirect("teacher_dashboard")

    enrollments = (
        Enrollment.objects
        .filter(
            class_level=class_level,
            term=current_term,
            student__active=True,
        )
        .select_related(
            "student",
            "class_level",
            "term",
        )
        .order_by(
            "student__surname",
            "student__first_name",
        )
    )

    # ------------------------------------------------------------
    # BUILD OVERALL GRADE DATA FOR PRINCIPAL'S OVERALL COMMENTS
    # ------------------------------------------------------------

    academic_grades = {}

    for enrollment in enrollments:
        scores = (
            Score.objects
            .filter(
                enrollment=enrollment,
                approved=True,
            )
            .select_related("subject")
        )

        totals = []

        for score in scores:
            totals.append(score.total)

        if totals:
            average = sum(totals) / len(totals)
            grade_record = GradeScale.objects.filter(
                minimum_score__lte=average,
                maximum_score__gte=average,
            ).first()

            if grade_record:
                academic_grades[enrollment.id] = grade_record.grade
            else:
                academic_grades[enrollment.id] = ""
        else:
            academic_grades[enrollment.id] = ""

    if request.method == "POST":
        errors = []

        valid_behaviour_values = dict(
            Enrollment.FORM_TEACHER_COMMENT_CHOICES
        )

        valid_academic_values = dict(
            Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
        )

        for enrollment in enrollments:

            # -------------------------
            # BEHAVIOUR COMMENT
            # -------------------------

            behaviour_field = (
                f"student_{enrollment.id}_comment"
            )

            behaviour_comment = request.POST.get(
                behaviour_field,
                ""
            ).strip()

            if (
                behaviour_comment
                and behaviour_comment not in valid_behaviour_values
            ):
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "invalid behaviour comment."
                )
                continue

            # -------------------------
            # ACADEMIC COMMENT
            # -------------------------

            academic_field = (
                f"student_{enrollment.id}_academic_comment"
            )

            academic_comment = request.POST.get(
                academic_field,
                ""
            ).strip()

            if (
                academic_comment
                and academic_comment not in valid_academic_values
            ):
                errors.append(
                    f"{enrollment.student.full_name}: "
                    "invalid principal's overall comment."
                )
                continue

            enrollment.form_teacher_comment = behaviour_comment
            enrollment.academic_performance_comment = academic_comment

            enrollment.save(
                update_fields=[
                    "form_teacher_comment",
                    "academic_performance_comment",
                ]
            )

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(
                request,
                "Form Teacher comments saved successfully.",
            )

        return redirect(
            "form_teacher_comments",
            class_id=class_level.id,
        )

    return render(
        request,
        "school/form_teacher_comments.html",
        {
            "teacher": account.teacher,
            "class_level": class_level,
            "current_term": current_term,
            "enrollments": enrollments,
            "comment_choices": (
                Enrollment.FORM_TEACHER_COMMENT_CHOICES
            ),
            "academic_comment_choices": (
                Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
            ),
            "academic_grades": academic_grades,
        },
    )


@login_required(login_url="/teacher-login/")
def email_student_result(request, student_id):
    """Email the student's existing official result PDF."""
    if request.method != "POST":
        messages.error(
            request,
            "Invalid request for emailing the result.",
        )
        return redirect("student_result", student_id=student_id)

    student = get_object_or_404(Student, id=student_id)

    if not student.email:
        messages.error(
            request,
            "This student does not have an email address. "
            "Add the student or parent/guardian email first.",
        )
        return redirect("student_result", student_id=student_id)

    # Generate the exact same PDF used by the existing Download PDF view.
    from .pdf_views import student_result_pdf

    pdf_response = student_result_pdf(request, student_id)

    if pdf_response.status_code != 200:
        messages.error(
            request,
            "The result PDF could not be generated. "
            "Make sure the result has been published.",
        )
        return redirect("student_result", student_id=student_id)

    from django.core.mail import EmailMessage

    email = EmailMessage(
        subject=(
            f"Academic Result - "
            f"{student.full_name}"
        ),
        body=(
            f"Dear Parent/Guardian,\n\n"
            f"Please find attached the academic result for "
            f"{student.full_name} "
            f"(Admission No. {student.admission_number}).\n\n"
            f"Regards,\n"
            f"Rock Foundation Academy and College"
        ),
        from_email=None,
        to=[student.email],
    )

    filename = (
        f"Student_Result_"
        f"{student.admission_number}.pdf"
    )

    email.attach(
        filename,
        pdf_response.content,
        "application/pdf",
    )

    try:
        email.send(fail_silently=False)

        messages.success(
            request,
            f"Result successfully emailed to {student.email}.",
        )

    except Exception:
        messages.error(
            request,
            "The result could not be emailed. "
            "Please check the email configuration and try again."
        )

    return redirect("student_result", student_id=student_id)

# ============================================================
# BROWSER ATTENDANCE
# ============================================================


# ============================================================
# BROWSER ATTENDANCE
# ============================================================

@login_required(login_url="/teacher-login/")
def teacher_attendance(request):
    """Browser daily attendance for the assigned Form Teacher class."""
    from datetime import date
    from django.db import transaction
    from .models import Attendance, ClassLevel, Enrollment, Term

    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        messages.error(request, "Teacher account not found.")
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        messages.error(request, "Your teacher account is inactive.")
        return redirect("teacher_login")

    assigned_classes = list(
        ClassLevel.objects
        .filter(form_teacher=account.teacher)
        .order_by("name")
    )

    if not assigned_classes:
        messages.error(
            request,
            "No Form Teacher class is assigned to your account."
        )
        return redirect("teacher_dashboard")

    if len(assigned_classes) > 1:
        messages.error(
            request,
            "More than one Form Teacher class is assigned to your account."
        )
        return redirect("teacher_dashboard")

    class_level = assigned_classes[0]

    current_term = (
        Term.objects
        .filter(is_current=True)
        .select_related("session")
        .order_by("-session_id", "-id")
        .first()
    )

    if current_term is None:
        messages.error(
            request,
            "There is no current academic term configured."
        )
        return redirect("teacher_dashboard")

    enrollments = list(
        Enrollment.objects
        .filter(
            class_level=class_level,
            term=current_term,
            student__active=True,
        )
        .select_related("student")
        .order_by(
            "student__surname",
            "student__first_name",
            "student__other_names",
        )
    )

    selected_date = request.POST.get("attendance_date") or request.GET.get(
        "date"
    )

    if selected_date:
        try:
            attendance_date = date.fromisoformat(selected_date)
        except ValueError:
            messages.error(
                request,
                "Invalid date. Please use YYYY-MM-DD."
            )
            attendance_date = date.today()
    else:
        attendance_date = date.today()

    if request.method == "POST":
        valid_statuses = {
            "PRESENT",
            "ABSENT",
            "LATE",
            "EXCUSED",
        }

        with transaction.atomic():
            for enrollment in enrollments:
                field_name = f"status_{enrollment.student.id}"
                status_value = request.POST.get(
                    field_name,
                    "PRESENT",
                ).upper()

                if status_value not in valid_statuses:
                    status_value = "PRESENT"

                Attendance.objects.update_or_create(
                    student=enrollment.student,
                    date=attendance_date,
                    defaults={
                        "enrollment": enrollment,
                        "status": status_value,
                        "marked_by": account,
                    },
                )

        messages.success(
            request,
            f"Attendance saved for {class_level.name} "
            f"on {attendance_date.strftime('%d %B %Y')}."
        )

    attendance_map = {
        record.student_id: record.status
        for record in Attendance.objects.filter(
            enrollment__in=enrollments,
            date=attendance_date,
        )
    }

    attendance_rows = []

    for enrollment in enrollments:
        attendance_rows.append({
            "student": enrollment.student,
            "status": attendance_map.get(
                enrollment.student.id,
                "PRESENT",
            ),
        })

    return render(
        request,
        "school/teacher_attendance.html",
        {
            "teacher": account.teacher,
            "class_level": class_level,
            "current_term": current_term,
            "attendance_date": attendance_date,
            "attendance_rows": attendance_rows,
        },
    )


@login_required(login_url="/teacher-login/")
def teacher_attendance_history(request):
    """Browser attendance history for the assigned Form Teacher class."""
    from .models import Attendance, ClassLevel, Enrollment, Term

    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        messages.error(request, "Teacher account not found.")
        return redirect("teacher_login")

    if not account.active or not account.teacher.active:
        messages.error(request, "Your teacher account is inactive.")
        return redirect("teacher_login")

    assigned_classes = list(
        ClassLevel.objects
        .filter(form_teacher=account.teacher)
        .order_by("name")
    )

    if not assigned_classes:
        messages.error(
            request,
            "No Form Teacher class is assigned to your account."
        )
        return redirect("teacher_dashboard")

    if len(assigned_classes) > 1:
        messages.error(
            request,
            "More than one Form Teacher class is assigned to your account."
        )
        return redirect("teacher_dashboard")

    class_level = assigned_classes[0]

    current_term = (
        Term.objects
        .filter(is_current=True)
        .select_related("session")
        .order_by("-session_id", "-id")
        .first()
    )

    if current_term is None:
        messages.error(
            request,
            "There is no current academic term configured."
        )
        return redirect("teacher_dashboard")

    enrollments = list(
        Enrollment.objects
        .filter(
            class_level=class_level,
            term=current_term,
            student__active=True,
        )
        .select_related("student")
        .order_by(
            "student__surname",
            "student__first_name",
            "student__other_names",
        )
    )

    student_id = request.GET.get("student_id", "").strip()

    selected_student = None

    if student_id:
        try:
            selected_student = next(
                (
                    enrollment.student
                    for enrollment in enrollments
                    if enrollment.student.id == int(student_id)
                ),
                None,
            )
        except (ValueError, TypeError):
            selected_student = None

    enrollment_ids = [enrollment.id for enrollment in enrollments]

    records = (
        Attendance.objects
        .filter(enrollment_id__in=enrollment_ids)
        .select_related("student")
        .order_by(
            "-date",
            "student__surname",
            "student__first_name",
        )
    )

    if selected_student is not None:
        records = records.filter(student=selected_student)

    history_rows = []

    for record in records:
        history_rows.append({
            "date": record.date,
            "student": record.student,
            "status": record.status,
        })

    summary = {}

    for enrollment in enrollments:
        student = enrollment.student

        student_records = Attendance.objects.filter(
            enrollment=enrollment,
        )

        present = student_records.filter(status="PRESENT").count()
        absent = student_records.filter(status="ABSENT").count()
        late = student_records.filter(status="LATE").count()
        excused = student_records.filter(status="EXCUSED").count()

        total = present + absent + late + excused

        summary[student.id] = {
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "total": total,
            "rate": (
                round((present + late) / total * 100, 1)
                if total
                else 0
            ),
        }

    return render(
        request,
        "school/teacher_attendance_history.html",
        {
            "teacher": account.teacher,
            "class_level": class_level,
            "current_term": current_term,
            "enrollments": enrollments,
            "selected_student": selected_student,
            "history_rows": history_rows,
            "summary_rows": [
                {
                    "student": enrollment.student,
                    "data": summary.get(enrollment.student.id, {}),
                }
                for enrollment in enrollments
                if (
                    selected_student is None
                    or selected_student.id == enrollment.student.id
                )
            ],
        },
    )


def official_homepage(request):
    return render(
        request,
        "school/official_homepage.html",
    )
