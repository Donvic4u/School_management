from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel, Enrollment, Score
from .result_views import get_current_term


class TeacherSubmitAllScoresAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            account = request.user.teacher_account
        except Exception:
            return Response(
                {
                    "success": False,
                    "message": "This account is not linked to a teacher account.",
                },
                status=403,
            )

        if not account.active or not account.teacher.active:
            return Response(
                {
                    "success": False,
                    "message": "This teacher account is inactive.",
                },
                status=403,
            )

        teacher = account.teacher

        assigned_classes = list(
            ClassLevel.objects.filter(
                form_teacher=teacher
            ).order_by("name")
        )

        if not assigned_classes:
            return Response(
                {
                    "success": False,
                    "message": "No Form Teacher class is currently assigned.",
                },
                status=403,
            )

        if len(assigned_classes) > 1:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Your account is assigned to more than one "
                        "Form Teacher class. Please contact the administrator."
                    ),
                },
                status=409,
            )

        assigned_class = assigned_classes[0]
        current_term = get_current_term()

        if current_term is None:
            return Response(
                {
                    "success": False,
                    "message": "No current academic term has been configured.",
                },
                status=409,
            )

        subject_id = request.data.get("subject_id")

        if not subject_id:
            return Response(
                {
                    "success": False,
                    "message": "subject_id is required.",
                },
                status=400,
            )

        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "subject_id must be a valid number.",
                },
                status=400,
            )

        class_subject = (
            assigned_class.class_subjects
            .filter(
                subject_id=subject_id,
                active=True,
            )
            .select_related("subject")
            .first()
        )

        if class_subject is None:
            return Response(
                {
                    "success": False,
                    "message": "This subject is not assigned to your class.",
                },
                status=404,
            )

        enrollments = list(
            Enrollment.objects.filter(
                class_level=assigned_class,
                term=current_term,
            ).select_related("student")
        )

        submitted_count = 0
        already_submitted_count = 0
        approved_count = 0
        incomplete_count = 0
        missing_count = 0
        incomplete_students = []

        for enrollment in enrollments:
            score = Score.objects.filter(
                enrollment=enrollment,
                subject=class_subject.subject,
            ).first()

            if score is None:
                missing_count += 1
                incomplete_students.append(
                    enrollment.student.full_name
                )
                continue

            if score.approved:
                approved_count += 1
                continue

            if score.submitted:
                already_submitted_count += 1
                continue

            values = [
                score.ca1_score,
                score.ca2_score,
                score.ca3_score,
                score.exam_score,
            ]

            if any(value is None for value in values):
                incomplete_count += 1
                incomplete_students.append(
                    enrollment.student.full_name
                )
                continue

            score.submitted = True
            score.save(update_fields=["submitted"])
            submitted_count += 1

        return Response(
            {
                "success": True,
                "message": "Score submission process completed.",
                "class": {
                    "id": assigned_class.id,
                    "name": assigned_class.name,
                },
                "subject": {
                    "id": class_subject.subject.id,
                    "code": class_subject.subject.code,
                    "name": class_subject.subject.name,
                },
                "summary": {
                    "submitted": submitted_count,
                    "already_submitted": already_submitted_count,
                    "approved": approved_count,
                    "incomplete": incomplete_count,
                    "missing": missing_count,
                    "total_students": len(enrollments),
                },
                "incomplete_students": incomplete_students,
            }
        )
