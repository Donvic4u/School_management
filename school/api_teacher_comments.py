from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import (
    ClassLevel,
    Enrollment,
    Student,
    TeacherAccount,
    Term,
)


def get_teacher_account(request):
    try:
        account = request.user.teacher_account
    except TeacherAccount.DoesNotExist:
        return None

    if not account.active or not account.teacher.active:
        return None

    return account


class TeacherCommentsAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = get_teacher_account(request)

        if account is None:
            return Response(
                {
                    "success": False,
                    "message": "Active teacher account required.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        class_levels = ClassLevel.objects.filter(
            form_teacher=account.teacher
        ).order_by("name")

        current_term = Term.objects.filter(
            is_current=True
        ).select_related("session").first()

        if current_term is None:
            return Response(
                {
                    "success": False,
                    "message": "There is no current academic term.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        classes = []

        for class_level in class_levels:
            enrollments = (
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

            students = []

            for enrollment in enrollments:
                students.append(
                    {
                        "id": enrollment.student.id,
                        "admission_number": (
                            enrollment.student.admission_number
                        ),
                        "name": enrollment.student.full_name,
                        "form_teacher_comment": (
                            enrollment.form_teacher_comment
                        ),
                        "academic_performance_comment": (
                            enrollment.academic_performance_comment
                        ),
                    }
                )

            classes.append(
                {
                    "id": class_level.id,
                    "name": class_level.name,
                    "students": students,
                }
            )

        return Response(
            {
                "success": True,
                "session": current_term.session.name,
                "term": current_term.name,
                "classes": classes,
                "form_teacher_comment_choices": [
                    {
                        "value": value,
                        "label": label,
                    }
                    for value, label
                    in Enrollment.FORM_TEACHER_COMMENT_CHOICES
                ],
                "academic_performance_comment_choices": [
                    {
                        "value": value,
                        "label": label,
                    }
                    for value, label
                    in Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
                ],
            }
        )

    def post(self, request):
        account = get_teacher_account(request)

        if account is None:
            return Response(
                {
                    "success": False,
                    "message": "Active teacher account required.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            student_id = int(request.data.get("student_id"))
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "A valid student_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        behaviour_comment = str(
            request.data.get(
                "form_teacher_comment",
                "",
            )
        ).strip()

        academic_comment = str(
            request.data.get(
                "academic_performance_comment",
                "",
            )
        ).strip()

        valid_behaviour_values = {
            value
            for value, label
            in Enrollment.FORM_TEACHER_COMMENT_CHOICES
        }

        valid_academic_values = {
            value
            for value, label
            in Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
        }

        if behaviour_comment not in valid_behaviour_values:
            return Response(
                {
                    "success": False,
                    "message": "Invalid Form Teacher comment.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if academic_comment not in valid_academic_values:
            return Response(
                {
                    "success": False,
                    "message": "Invalid academic performance comment.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_term = Term.objects.filter(
            is_current=True
        ).first()

        if current_term is None:
            return Response(
                {
                    "success": False,
                    "message": "There is no current academic term.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        enrollment = (
            Enrollment.objects
            .filter(
                student_id=student_id,
                term=current_term,
                class_level__form_teacher=account.teacher,
                student__active=True,
            )
            .select_related(
                "student",
                "class_level",
                "term",
            )
            .first()
        )

        if enrollment is None:
            return Response(
                {
                    "success": False,
                    "message": (
                        "You are not authorized to manage comments "
                        "for this student."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        enrollment.form_teacher_comment = behaviour_comment
        enrollment.academic_performance_comment = academic_comment

        enrollment.save(
            update_fields=[
                "form_teacher_comment",
                "academic_performance_comment",
            ]
        )

        return Response(
            {
                "success": True,
                "message": "Form Teacher comments saved successfully.",
                "student": {
                    "id": enrollment.student.id,
                    "admission_number": (
                        enrollment.student.admission_number
                    ),
                    "name": enrollment.student.full_name,
                    "form_teacher_comment": (
                        enrollment.form_teacher_comment
                    ),
                    "academic_performance_comment": (
                        enrollment.academic_performance_comment
                    ),
                },
            }
        )
