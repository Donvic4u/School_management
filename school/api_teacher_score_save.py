from decimal import Decimal, InvalidOperation

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel, ClassSubject, Enrollment, Score, Term


class TeacherScoreSaveAPIView(APIView):
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

        current_term = (
            Term.objects.filter(is_current=True)
            .select_related("session")
            .order_by("-session_id", "-id")
            .first()
        )

        if current_term is None:
            return Response(
                {
                    "success": False,
                    "message": "No current academic term has been configured.",
                },
                status=409,
            )

        try:
            student_id = int(request.data.get("student_id"))
            subject_id = int(request.data.get("subject_id"))
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "Valid student_id and subject_id are required.",
                },
                status=400,
            )

        enrollment = (
            Enrollment.objects.filter(
                student_id=student_id,
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
                    "message": "This student is not in your assigned class.",
                },
                status=403,
            )

        class_subject = (
            ClassSubject.objects.filter(
                class_level=assigned_class,
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
                status=403,
            )

        score, created = Score.objects.get_or_create(
            enrollment=enrollment,
            subject=class_subject.subject,
        )

        if not created and (score.approved or score.submitted):
            return Response(
                {
                    "success": False,
                    "message": (
                        "This score has already been submitted or approved "
                        "and cannot be edited."
                    ),
                    "submitted": score.submitted,
                    "approved": score.approved,
                },
                status=403,
            )

        field_limits = {
            "ca1": Decimal("10"),
            "ca2": Decimal("10"),
            "ca3": Decimal("10"),
            "exam": Decimal("70"),
        }

        values = {}

        for field, maximum in field_limits.items():
            raw_value = request.data.get(field, None)

            if raw_value is None or str(raw_value).strip() == "":
                values[field] = None
                continue

            try:
                value = Decimal(str(raw_value).strip())
            except (InvalidOperation, ValueError):
                return Response(
                    {
                        "success": False,
                        "message": f"Invalid {field.upper()} score.",
                    },
                    status=400,
                )

            if value < Decimal("0") or value > maximum:
                return Response(
                    {
                        "success": False,
                        "message": (
                            f"{field.upper()} must be between "
                            f"0 and {maximum}."
                        ),
                    },
                    status=400,
                )

            values[field] = value

        score.ca1_score = values["ca1"]
        score.ca2_score = values["ca2"]
        score.ca3_score = values["ca3"]
        score.exam_score = values["exam"]

        score.submitted = False
        score.approved = False
        score.save()

        return Response(
            {
                "success": True,
                "message": "Score saved as draft.",
                "student": {
                    "id": enrollment.student.id,
                    "admission_number": enrollment.student.admission_number,
                    "name": enrollment.student.full_name,
                },
                "subject": {
                    "id": class_subject.subject.id,
                    "code": class_subject.subject.code,
                    "name": class_subject.subject.name,
                },
                "score": {
                    "id": score.id,
                    "ca1": float(score.ca1_score) if score.ca1_score is not None else None,
                    "ca2": float(score.ca2_score) if score.ca2_score is not None else None,
                    "ca3": float(score.ca3_score) if score.ca3_score is not None else None,
                    "exam": float(score.exam_score) if score.exam_score is not None else None,
                    "submitted": score.submitted,
                    "approved": score.approved,
                },
            },
            status=200,
        )
