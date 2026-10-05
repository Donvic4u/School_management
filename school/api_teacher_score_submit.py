from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel, Enrollment, Score
from .result_views import get_current_term


class TeacherScoreSubmitAPIView(APIView):
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

        enrollment_id = request.data.get("enrollment_id")
        subject_id = request.data.get("subject_id")

        if not enrollment_id or not subject_id:
            return Response(
                {
                    "success": False,
                    "message": "enrollment_id and subject_id are required.",
                },
                status=400,
            )

        try:
            enrollment_id = int(enrollment_id)
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "enrollment_id and subject_id must be valid numbers.",
                },
                status=400,
            )

        enrollment = (
            Enrollment.objects
            .filter(
                id=enrollment_id,
                class_level=assigned_class,
                term=current_term,
            )
            .select_related("student")
            .first()
        )

        if enrollment is None:
            return Response(
                {
                    "success": False,
                    "message": "Student is not in your assigned class.",
                },
                status=404,
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

        score = Score.objects.filter(
            enrollment=enrollment,
            subject=class_subject.subject,
        ).first()

        if score is None:
            return Response(
                {
                    "success": False,
                    "message": "No score draft exists for this student and subject.",
                },
                status=404,
            )

        if score.approved:
            return Response(
                {
                    "success": False,
                    "message": "This score has already been approved and is locked.",
                },
                status=409,
            )

        if score.submitted:
            return Response(
                {
                    "success": False,
                    "message": "This score has already been submitted and is locked.",
                },
                status=409,
            )

        values = [
            score.ca1_score,
            score.ca2_score,
            score.ca3_score,
            score.exam_score,
        ]

        if any(value is None for value in values):
            return Response(
                {
                    "success": False,
                    "message": (
                        "All CA1, CA2, CA3 and Exam scores must be entered "
                        "before submission."
                    ),
                },
                status=400,
            )

        score.submitted = True
        score.save(update_fields=["submitted"])

        return Response(
            {
                "success": True,
                "message": "Score submitted successfully.",
                "student": {
                    "id": enrollment.student.id,
                    "name": enrollment.student.full_name,
                    "admission_number": enrollment.student.admission_number,
                },
                "subject": {
                    "id": class_subject.subject.id,
                    "code": class_subject.subject.code,
                    "name": class_subject.subject.name,
                },
                "score": {
                    "id": score.id,
                    "ca1": float(score.ca1_score),
                    "ca2": float(score.ca2_score),
                    "ca3": float(score.ca3_score),
                    "exam": float(score.exam_score),
                    "total": float(score.total),
                    "submitted": score.submitted,
                    "approved": score.approved,
                },
            }
        )
