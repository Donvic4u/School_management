from django.contrib import admin
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
    ResultPublication,
    ResultAccess,
)


@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email")


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_current")
    list_filter = ("is_current",)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("name", "session", "is_current")
    list_filter = ("session", "name", "is_current")


@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "form_teacher")
    list_filter = ("form_teacher",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "max_ca",
        "max_exam",
        "active",
    )
    list_filter = ("active",)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = (
        "staff_id",
        "surname",
        "first_name",
        "other_names",
        "phone",
        "email",
        "active",
    )
    list_filter = ("active",)
    search_fields = (
        "staff_id",
        "surname",
        "first_name",
        "other_names",
    )


@admin.register(TeacherAccount)
class TeacherAccountAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "user",
        "active",
    )
    list_filter = ("active",)
    search_fields = (
        "teacher__staff_id",
        "teacher__surname",
        "teacher__first_name",
        "user__username",
    )


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "class_level",
        "subject",
        "active",
    )
    list_filter = (
        "teacher",
        "class_level",
        "subject",
        "active",
    )
    search_fields = (
        "teacher__staff_id",
        "teacher__surname",
        "teacher__first_name",
        "class_level__name",
        "subject__name",
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_number",
        "surname",
        "first_name",
        "gender",
        "current_class",
        "passport_photo_status",
        "active",
    )
    list_filter = (
        "gender",
        "current_class",
        "active",
    )
    search_fields = (
        "admission_number",
        "surname",
        "first_name",
        "other_names",
    )

    @admin.display(
        description="Passport Photo"
    )
    def passport_photo_status(self, obj):
        return "Uploaded" if obj.passport_photo else "Not uploaded"


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "class_level",
        "term",
    )
    list_filter = (
        "class_level",
        "term",
    )
    search_fields = (
        "student__admission_number",
        "student__surname",
        "student__first_name",
    )


def approve_scores(modeladmin, request, queryset):
    from .models import Enrollment, Term
    from .promotion_engine import (
        evaluate_student,
        get_next_class,
        get_next_session,
    )

    # --------------------------------------------------------
    # Capture affected enrollments BEFORE approval.
    # --------------------------------------------------------

    affected_enrollment_ids = list(
        queryset.filter(
            submitted=True,
            approved=False,
        )
        .values_list(
            "enrollment_id",
            flat=True,
        )
        .distinct()
    )

    # --------------------------------------------------------
    # Approve and lock selected scores.
    # --------------------------------------------------------

    updated = queryset.filter(
        submitted=True,
        approved=False,
    ).update(
        approved=True,
    )

    auto_promoted = 0
    completed_sss3 = 0
    waiting_for_next_session = 0

    # --------------------------------------------------------
    # Automatic promotion applies ONLY to Third Term.
    # --------------------------------------------------------

    if affected_enrollment_ids:

        third_term_enrollments = (
            Enrollment.objects
            .filter(
                id__in=affected_enrollment_ids,
                term__name=Term.THIRD,
            )
            .select_related(
                "student",
                "class_level",
                "term",
            )
        )

        for enrollment in third_term_enrollments:

            # ------------------------------------------------
            # Evaluate using approved scores only.
            # ------------------------------------------------

            evaluation = evaluate_student(enrollment)

            if not evaluation["eligible"]:
                continue

            # ------------------------------------------------
            # SSS3 students complete school.
            # ------------------------------------------------

            if enrollment.class_level.name in {
                "SSS 3A",
                "SSS 3B",
            }:
                completed_sss3 += 1
                continue

            # ------------------------------------------------
            # Determine destination class/session.
            # ------------------------------------------------

            next_class = get_next_class(
                enrollment.class_level
            )

            next_session = get_next_session(
                enrollment.term.session
            )

            if next_class is None:
                continue

            # Do NOT create the next academic session
            # automatically.
            if next_session is None:
                waiting_for_next_session += 1
                continue

            destination_term = Term.objects.filter(
                session=next_session,
                name=Term.FIRST,
            ).first()

            if destination_term is None:
                waiting_for_next_session += 1
                continue

            # ------------------------------------------------
            # Prevent duplicate destination enrollment.
            # ------------------------------------------------

            student = enrollment.student

            already_enrolled = Enrollment.objects.filter(
                student=student,
                term=destination_term,
            ).exists()

            if already_enrolled:
                continue

            # ------------------------------------------------
            # Create the new enrollment.
            #
            # Historical enrollment and scores remain intact.
            # ------------------------------------------------

            Enrollment.objects.create(
                student=student,
                class_level=next_class,
                term=destination_term,
            )

            student.current_class = next_class
            student.save(
                update_fields=["current_class"]
            )

            auto_promoted += 1

    # --------------------------------------------------------
    # Admin feedback.
    # --------------------------------------------------------

    message = (
        f"{updated} score(s) approved and locked."
    )

    if auto_promoted:
        message += (
            f" {auto_promoted} student(s) automatically promoted."
        )

    if completed_sss3:
        message += (
            f" {completed_sss3} SSS3 student(s) completed SSS3."
        )

    if waiting_for_next_session:
        message += (
            f" {waiting_for_next_session} eligible student(s) "
            "are waiting for the next academic session to be created."
        )

    modeladmin.message_user(
        request,
        message,
    )

approve_scores.short_description = "Approve selected submitted scores"


def return_scores(modeladmin, request, queryset):
    updated = queryset.filter(
        approved=False,
    ).update(
        submitted=False,
        approved=False,
    )

    modeladmin.message_user(
        request,
        f"{updated} score(s) returned to draft."
    )


return_scores.short_description = "Return selected scores to draft"


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = (
        "student_name",
        "subject",
        "ca1_score",
        "ca2_score",
        "ca3_score",
        "ca_total_display",
        "exam_score",
        "total_display",
        "submitted",
        "approved",
    )
    list_filter = (
        "subject",
        "submitted",
        "approved",
    )

    actions = [
        approve_scores,
        return_scores,
    ]
    search_fields = (
        "enrollment__student__admission_number",
        "enrollment__student__surname",
        "enrollment__student__first_name",
        "subject__name",
    )

    @admin.display(
        description="Student",
        ordering="enrollment__student__surname",
    )
    def student_name(self, obj):
        return obj.enrollment.student.full_name

    @admin.display(
        description="CA /30",
        ordering="ca1_score",
    )
    def ca_total_display(self, obj):
        return obj.ca_total

    @admin.display(
        description="Total /100",
        ordering="exam_score",
    )
    def total_display(self, obj):
        return obj.total


@admin.register(GradeScale)
class GradeScaleAdmin(admin.ModelAdmin):
    list_display = (
        "minimum_score",
        "maximum_score",
        "grade",
        "remark",
    )
    ordering = ("-minimum_score",)


# ============================================================
# RESULT PUBLICATION ADMIN
# ============================================================

def publish_results(modeladmin, request, queryset):
    from django.utils import timezone
    from .models import Score

    published_count = 0
    blocked_count = 0

    for publication in queryset:

        scores = Score.objects.filter(
            enrollment__class_level=publication.class_level,
            enrollment__term=publication.term,
        )

        total_scores = scores.count()
        approved_scores = scores.filter(
            approved=True
        ).count()

        if total_scores == 0:
            blocked_count += 1
            continue

        if approved_scores != total_scores:
            blocked_count += 1
            continue

        publication.published = True
        publication.published_at = timezone.now()
        publication.save(
            update_fields=[
                "published",
                "published_at",
            ]
        )

        published_count += 1

    modeladmin.message_user(
        request,
        f"{published_count} result publication(s) published. "
        f"{blocked_count} publication(s) blocked because "
        f"not all scores are approved or no scores exist."
    )


publish_results.short_description = "Publish selected results"


def unpublish_results(modeladmin, request, queryset):

    updated = queryset.update(
        published=False,
        published_at=None,
    )

    modeladmin.message_user(
        request,
        f"{updated} result publication(s) unpublished."
    )


unpublish_results.short_description = "Unpublish selected results"


@admin.register(ResultPublication)
class ResultPublicationAdmin(admin.ModelAdmin):

    list_display = (
        "session",
        "term",
        "class_level",
        "published",
        "published_at",
    )

    list_filter = (
        "session",
        "term",
        "class_level",
        "published",
    )

    search_fields = (
        "session__name",
        "class_level__name",
    )

    actions = [
        publish_results,
        unpublish_results,
    ]


@admin.register(ResultAccess)
class ResultAccessAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "student_admission_number",
        "pin",
        "active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "active",
    )

    search_fields = (
        "student__admission_number",
        "student__surname",
        "student__first_name",
        "pin",
    )

    list_editable = (
        "pin",
        "active",
    )

    @admin.display(
        description="Admission Number"
    )
    def student_admission_number(self, obj):
        return obj.student.admission_number
