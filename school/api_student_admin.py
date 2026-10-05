from django.contrib.auth.hashers import make_password
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import Student


class AdminStudentLoginSettingsAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, student_id):
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {
                    "success": False,
                    "message": "Admin access required."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Student not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if "pin" in request.data:
            pin = str(request.data.get("pin", "")).strip()

            if not pin:
                return Response(
                    {
                        "success": False,
                        "message": "PIN cannot be empty."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not pin.isdigit():
                return Response(
                    {
                        "success": False,
                        "message": "PIN must contain numbers only."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if len(pin) < 4 or len(pin) > 8:
                return Response(
                    {
                        "success": False,
                        "message": "PIN must be between 4 and 8 digits."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            student.login_pin = make_password(pin)

        if "student_login_active" in request.data:
            value = request.data.get("student_login_active")

            if isinstance(value, bool):
                student.student_login_active = value
            elif str(value).lower() in ("true", "1", "yes"):
                student.student_login_active = True
            elif str(value).lower() in ("false", "0", "no"):
                student.student_login_active = False
            else:
                return Response(
                    {
                        "success": False,
                        "message": "student_login_active must be true or false."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        student.save(
            update_fields=[
                "login_pin",
                "student_login_active",
            ]
        )

        return Response(
            {
                "success": True,
                "message": "Student login settings updated successfully.",
                "student": {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "student_login_active": student.student_login_active,
                    "pin_set": bool(student.login_pin),
                },
            }
        )
