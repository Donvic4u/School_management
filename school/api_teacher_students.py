from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel, Enrollment, Term


class TeacherStudentsAPIView(APIView):
    """
    Return students belonging to the authenticated teacher's
    assigned Form Teacher class for the current academic term.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
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
            ClassLevel.objects
            .filter(form_teacher=teacher)
            .order_by("name")
        )

        if not assigned_classes:
            return Response(
                {
                    "success": True,
                    "teacher": {
                        "name": teacher.full_name,
                        "username": request.user.username,
                    },
                    "class": None,
                    "students": [],
                    "count": 0,
                    "message": "No Form Teacher class is currently assigned.",
                }
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
            Term.objects
            .filter(is_current=True)
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

        enrollments = (
            Enrollment.objects
            .filter(
                class_level=assigned_class,
                term=current_term,
            )
            .select_related("student")
            .order_by(
                "student__surname",
                "student__first_name",
                "student__other_names",
            )
        )

        students = []

        for enrollment in enrollments:
            student = enrollment.student

            students.append(
                {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "surname": student.surname,
                    "first_name": student.first_name,
                    "other_names": student.other_names,
                    "full_name": student.full_name,
                    "gender": student.gender,
                    "phone_number": student.phone_number,
                    "email": student.email,
                        "passport_photo_url": (
                            request.build_absolute_uri(student.passport_photo.url)
                            if student.passport_photo
                            else ""
                        ),
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
            )

        return Response(
            {
                "success": True,
                "teacher": {
                    "name": teacher.full_name,
                    "username": request.user.username,
                },
                "class": {
                    "id": assigned_class.id,
                    "name": assigned_class.name,
                },
                "term": {
                    "id": current_term.id,
                    "name": str(current_term),
                },
                "count": len(students),
                "students": students,
            }
        )
