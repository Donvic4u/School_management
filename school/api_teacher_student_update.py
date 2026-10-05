from datetime import date

from django.db import transaction
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel, Enrollment, Student, TeacherAccount, Term


class TeacherStudentUpdateAPIView(APIView):
    """
    Allow a Form Teacher to update basic details of a student
    belonging to the teacher's assigned Form Teacher class
    for the current academic term.

    Teachers cannot change:
    - admission number
    - class
    - active status
    - login PIN
    - scores
    - attendance
    - comments
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_teacher_context(self, request):
        try:
            account = request.user.teacher_account
        except TeacherAccount.DoesNotExist:
            return None, None, None, Response(
                {
                    "success": False,
                    "message": "This account is not linked to a teacher account.",
                },
                status=403,
            )

        if not account.active or not account.teacher.active:
            return None, None, None, Response(
                {
                    "success": False,
                    "message": "This teacher account is inactive.",
                },
                status=403,
            )

        teacher = account.teacher

        assigned_classes = list(
            ClassLevel.objects
            .filter(form_teacher=teacher)
            .order_by("name")
        )

        if not assigned_classes:
            return None, None, None, Response(
                {
                    "success": False,
                    "message": "You are not currently assigned as a Form Teacher to any class.",
                },
                status=403,
            )

        if len(assigned_classes) > 1:
            return None, None, None, Response(
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
            Term.objects
            .filter(is_current=True)
            .select_related("session")
            .order_by("-session_id", "-id")
            .first()
        )

        if current_term is None:
            return None, None, None, Response(
                {
                    "success": False,
                    "message": "No current academic term has been configured.",
                },
                status=409,
            )

        return account, assigned_class, current_term, None

    def _student_data(self, student, assigned_class):
        return {
            "id": student.id,
            "admission_number": student.admission_number,
            "surname": student.surname,
            "first_name": student.first_name,
            "other_names": student.other_names,
            "full_name": student.full_name,
            "gender": student.gender,
            "phone_number": student.phone_number,
            "email": student.email,
            "date_of_birth": (
                student.date_of_birth.isoformat()
                if student.date_of_birth
                else None
            ),
            "date_admitted": (
                student.date_admitted.isoformat()
                if student.date_admitted
                else None
            ),
            "active": student.active,
            "class": assigned_class.name,
        }

    def patch(self, request, student_id):
        account, assigned_class, current_term, error = self._get_teacher_context(
            request
        )

        if error:
            return error

        enrollment = (
            Enrollment.objects
            .filter(
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
                    "message": (
                        "This student does not belong to your assigned "
                        "Form Teacher class for the current academic term."
                    ),
                },
                status=403,
            )

        student = enrollment.student

        allowed_fields = [
            "surname",
            "first_name",
            "other_names",
            "gender",
            "date_of_birth",
            "date_admitted",
            "phone_number",
            "email",
        ]

        data = request.data

        for field in allowed_fields:
            if field not in data:
                continue

            value = data.get(field)

            if value is None:
                value = ""

            if isinstance(value, str):
                value = value.strip()

            if field in ("date_of_birth", "date_admitted"):
                if value == "":
                    parsed_date = None
                else:
                    try:
                        parsed_date = date.fromisoformat(str(value))
                    except (ValueError, TypeError):
                        return Response(
                            {
                                "success": False,
                                "message": (
                                    f"Invalid {field}. Use YYYY-MM-DD."
                                ),
                            },
                            status=400,
                        )

                setattr(student, field, parsed_date)

            else:
                setattr(student, field, value)

        # Never allow the teacher to move the student out of this class.
        student.current_class = assigned_class

        with transaction.atomic():
            student.save(
                update_fields=[
                    "surname",
                    "first_name",
                    "other_names",
                    "gender",
                    "date_of_birth",
                    "date_admitted",
                    "phone_number",
                    "email",
                    "current_class",
                ]
            )

        return Response(
            {
                "success": True,
                "message": "Student details updated successfully.",
                "student": self._student_data(student, assigned_class),
            }
        )
