from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Student


class AdminStudentsAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response(
                {
                    "success": False,
                    "message": "Administrator access is required.",
                },
                status=403,
            )

        students = Student.objects.select_related(
            "current_class"
        ).order_by(
            "surname",
            "first_name",
            "other_names",
        )

        search = request.query_params.get("search", "").strip()
        class_name = request.query_params.get("class", "").strip()
        active_filter = request.query_params.get("active", "").strip().lower()

        if search:
            from django.db.models import Q

            students = students.filter(
                Q(admission_number__icontains=search)
                | Q(surname__icontains=search)
                | Q(first_name__icontains=search)
                | Q(other_names__icontains=search)
            )

        if class_name:
            students = students.filter(
                current_class__name=class_name
            )

        if active_filter == "active":
            students = students.filter(active=True)

        elif active_filter == "inactive":
            students = students.filter(active=False)

        elif active_filter not in ("", "all"):
            return Response(
                {
                    "success": False,
                    "message": (
                        "Invalid active filter. "
                        "Use: all, active or inactive."
                    ),
                },
                status=400,
            )

        data = []

        for student in students:
            data.append(
                {
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
                }
            )

        return Response(
            {
                "success": True,
                "count": len(data),
                "filters": {
                    "search": search,
                    "class": class_name,
                    "active": active_filter or "all",
                },
                "students": data,
            }
        )
