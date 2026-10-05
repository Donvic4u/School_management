from django.contrib.auth.hashers import check_password
from django.core import signing
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import Student


STUDENT_TOKEN_SALT = "student-portal-auth"
STUDENT_TOKEN_MAX_AGE = 60 * 60 * 24 * 7


def get_authenticated_student(request):
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:].strip()

    if not token:
        return None

    try:
        data = signing.loads(
            token,
            salt=STUDENT_TOKEN_SALT,
            max_age=STUDENT_TOKEN_MAX_AGE,
        )
    except signing.BadSignature:
        return None
    except signing.SignatureExpired:
        return None

    student_id = data.get("student_id")

    if not student_id:
        return None

    return Student.objects.filter(
        id=student_id,
        active=True,
        student_login_active=True,
    ).first()


class StudentLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        admission_number = str(
            request.data.get("admission_number", "")
        ).strip()

        pin = str(
            request.data.get("pin", "")
        ).strip()

        if not admission_number or not pin:
            return Response(
                {
                    "success": False,
                    "message": "Admission number and PIN are required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = Student.objects.filter(
            admission_number__iexact=admission_number,
            active=True,
            student_login_active=True,
        ).first()

        if student is None or not student.login_pin:
            return Response(
                {
                    "success": False,
                    "message": "Invalid admission number or PIN."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not check_password(pin, student.login_pin):
            return Response(
                {
                    "success": False,
                    "message": "Invalid admission number or PIN."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = signing.dumps(
            {
                "student_id": student.id,
                "admission_number": student.admission_number,
            },
            salt=STUDENT_TOKEN_SALT,
        )

        return Response(
            {
                "success": True,
                "message": "Student login successful.",
                "token": token,
                "student": {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "name": student.full_name,
                    "gender": student.gender,
                    "class": (
                        student.current_class.name
                        if student.current_class
                        else ""
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )
