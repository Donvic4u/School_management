from datetime import date

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Student


class AdminStudentUpdateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, student_id):
        if not request.user.is_staff:
            return Response(
                {
                    "success": False,
                    "message": "Administrator access is required.",
                },
                status=403,
            )

        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Student not found.",
                },
                status=404,
            )

        if "surname" in request.data:
            surname = str(request.data.get("surname", "")).strip()

            if not surname:
                return Response(
                    {
                        "success": False,
                        "message": "Surname cannot be empty.",
                    },
                    status=400,
                )

            student.surname = surname

        if "first_name" in request.data:
            first_name = str(
                request.data.get("first_name", "")
            ).strip()

            if not first_name:
                return Response(
                    {
                        "success": False,
                        "message": "First name cannot be empty.",
                    },
                    status=400,
                )

            student.first_name = first_name

        if "other_names" in request.data:
            student.other_names = str(
                request.data.get("other_names", "")
            ).strip()

        if "gender" in request.data:
            gender = str(
                request.data.get("gender", "")
            ).strip()

            if gender not in {"Male", "Female"}:
                return Response(
                    {
                        "success": False,
                        "message": "Gender must be Male or Female.",
                    },
                    status=400,
                )

            student.gender = gender

        if "phone_number" in request.data:
            student.phone_number = str(
                request.data.get("phone_number", "")
            ).strip()

        if "email" in request.data:
            student.email = str(
                request.data.get("email", "")
            ).strip()

        if "date_of_birth" in request.data:
            dob = request.data.get("date_of_birth")

            if dob in (None, ""):
                student.date_of_birth = None
            else:
                try:
                    student.date_of_birth = date.fromisoformat(
                        str(dob)
                    )
                except ValueError:
                    return Response(
                        {
                            "success": False,
                            "message": (
                                "Invalid date_of_birth. "
                                "Use YYYY-MM-DD."
                            ),
                        },
                        status=400,
                    )

        if "date_admitted" in request.data:
            admitted = request.data.get("date_admitted")

            if admitted in (None, ""):
                student.date_admitted = None
            else:
                try:
                    student.date_admitted = date.fromisoformat(
                        str(admitted)
                    )
                except ValueError:
                    return Response(
                        {
                            "success": False,
                            "message": (
                                "Invalid date_admitted. "
                                "Use YYYY-MM-DD."
                            ),
                        },
                        status=400,
                    )

        if "active" in request.data:
            active = request.data.get("active")

            if isinstance(active, bool):
                student.active = active
            elif str(active).lower() in {"true", "1"}:
                student.active = True
            elif str(active).lower() in {"false", "0"}:
                student.active = False
            else:
                return Response(
                    {
                        "success": False,
                        "message": "Active must be true or false.",
                    },
                    status=400,
                )

        student.save()

        return Response(
            {
                "success": True,
                "message": "Student updated successfully.",
                "student": {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "name": student.full_name,
                    "surname": student.surname,
                    "first_name": student.first_name,
                    "other_names": student.other_names,
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
                    "class": (
                        student.current_class.name
                        if student.current_class
                        else ""
                    ),
                    "active": student.active,
                },
            }
        )
