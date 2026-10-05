from datetime import date
import re

from django.db import transaction
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Student, Enrollment, Term, ClassLevel


class TeacherStudentAddAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            account = request.user.teacher_account
        except Exception:
            return Response(
                {
                    "success": False,
                    "message": "Teacher account not found.",
                },
                status=403,
            )

        if not account.is_active:
            return Response(
                {
                    "success": False,
                    "message": "Teacher account is inactive.",
                },
                status=403,
            )

        teacher = account.teacher

        if teacher is None or not teacher.is_active:
            return Response(
                {
                    "success": False,
                    "message": "Teacher account is inactive.",
                },
                status=403,
            )

        assigned_classes = list(
            ClassLevel.objects
            .filter(form_teacher=teacher)
            .order_by("name")
        )

        if not assigned_classes:
            return Response(
                {
                    "success": False,
                    "message": "You are not assigned as a Form Teacher.",
                },
                status=403,
            )

        if len(assigned_classes) > 1:
            return Response(
                {
                    "success": False,
                    "message": "You are assigned to more than one form class. Contact the administrator.",
                },
                status=403,
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
                    "message": "No current term is configured.",
                },
                status=400,
            )

        surname = str(request.data.get("surname", "")).strip()
        first_name = str(request.data.get("first_name", "")).strip()
        other_names = str(request.data.get("other_names", "")).strip()
        gender = str(request.data.get("gender", "")).strip()
        phone_number = str(request.data.get("phone_number", "")).strip()
        email = str(request.data.get("email", "")).strip()
        date_of_birth = str(request.data.get("date_of_birth", "")).strip()
        date_admitted = str(request.data.get("date_admitted", "")).strip()

        if not surname:
            return Response(
                {"success": False, "message": "Surname is required."},
                status=400,
            )

        if not first_name:
            return Response(
                {"success": False, "message": "First name is required."},
                status=400,
            )

        if gender not in ("Male", "Female"):
            return Response(
                {
                    "success": False,
                    "message": "Gender must be Male or Female.",
                },
                status=400,
            )

        parsed_dob = None
        parsed_date_admitted = None

        if date_of_birth:
            try:
                parsed_dob = date.fromisoformat(date_of_birth)
            except ValueError:
                return Response(
                    {
                        "success": False,
                        "message": "Date of birth must use YYYY-MM-DD format.",
                    },
                    status=400,
                )

        if date_admitted:
            try:
                parsed_date_admitted = date.fromisoformat(date_admitted)
            except ValueError:
                return Response(
                    {
                        "success": False,
                        "message": "Date admitted must use YYYY-MM-DD format.",
                    },
                    status=400,
                )

        with transaction.atomic():
            numbers = []

            for admission_number in Student.objects.values_list(
                "admission_number",
                flat=True,
            ):
                match = re.fullmatch(
                    r"RFC(\d+)",
                    str(admission_number).strip().upper(),
                )
                if match:
                    numbers.append(int(match.group(1)))

            next_number = max(numbers, default=0) + 1
            admission_number = f"RFC{next_number:03d}"

            while Student.objects.filter(
                admission_number__iexact=admission_number
            ).exists():
                next_number += 1
                admission_number = f"RFC{next_number:03d}"

            student = Student.objects.create(
                admission_number=admission_number,
                surname=surname,
                first_name=first_name,
                other_names=other_names,
                gender=gender,
                date_of_birth=parsed_dob,
                date_admitted=parsed_date_admitted,
                current_class=assigned_class,
                phone_number=phone_number,
                email=email,
                active=True,
            )

            Enrollment.objects.update_or_create(
                student=student,
                term=current_term,
                defaults={
                    "class_level": assigned_class,
                },
            )

        return Response(
            {
                "success": True,
                "message": "Student added successfully.",
                "student": {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "surname": student.surname,
                    "first_name": student.first_name,
                    "other_names": student.other_names,
                    "full_name": student.get_full_name(),
                    "gender": student.gender,
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
                    "phone_number": student.phone_number,
                    "email": student.email,
                    "active": student.active,
                    "class": assigned_class.name,
                    "term": current_term.name,
                    "session": current_term.session.name,
                },
            },
            status=201,
        )
