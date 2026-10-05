from datetime import date

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Attendance, ClassLevel, Enrollment, Term, TeacherAccount


class TeacherAttendanceAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_teacher(self, request):
        try:
            return TeacherAccount.objects.select_related("teacher").get(
                user=request.user
            )
        except TeacherAccount.DoesNotExist:
            return None

    def get_assigned_class(self, teacher):
        classes = list(
            ClassLevel.objects
            .filter(form_teacher=teacher.teacher)
            .order_by("name")
        )

        if not classes:
            return None, "No form class is assigned to this teacher."

        if len(classes) > 1:
            return None, "More than one form class is assigned to this teacher."

        return classes[0], None

    def get_current_term(self):
        return (
            Term.objects
            .filter(is_current=True)
            .select_related("session")
            .order_by("-session_id", "-id")
            .first()
        )

    def get(self, request):
        teacher = self.get_teacher(request)

        if teacher is None:
            return Response(
                {"detail": "Teacher account not found."},
                status=403,
            )

        assigned_class, error = self.get_assigned_class(teacher)

        if error:
            return Response({"detail": error}, status=400)

        current_term = self.get_current_term()

        if current_term is None:
            return Response(
                {"detail": "No current academic term is configured."},
                status=400,
            )

        requested_date = request.query_params.get("date")

        if requested_date:
            try:
                attendance_date = date.fromisoformat(requested_date)
            except ValueError:
                return Response(
                    {"detail": "Invalid date. Use YYYY-MM-DD."},
                    status=400,
                )
        else:
            attendance_date = date.today()

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

        attendance_map = {
            record.student_id: record.status
            for record in Attendance.objects.filter(
                enrollment__in=enrollments,
                date=attendance_date,
            )
        }

        students = []

        for enrollment in enrollments:
            student = enrollment.student

            students.append({
                "student_id": student.id,
                "admission_number": student.admission_number,
                "full_name": student.full_name,
                "gender": student.gender,
                "status": attendance_map.get(
                    student.id,
                    "PRESENT",
                ),
            })

        return Response({
            "date": attendance_date.isoformat(),
            "class": assigned_class.name,
            "term": current_term.name,
            "session": current_term.session.name,
            "students": students,
        })

    def post(self, request):
        teacher = self.get_teacher(request)

        if teacher is None:
            return Response(
                {"detail": "Teacher account not found."},
                status=403,
            )

        assigned_class, error = self.get_assigned_class(teacher)

        if error:
            return Response({"detail": error}, status=400)

        current_term = self.get_current_term()

        if current_term is None:
            return Response(
                {"detail": "No current academic term is configured."},
                status=400,
            )

        attendance_date = request.data.get("date")

        if attendance_date:
            try:
                attendance_date = date.fromisoformat(attendance_date)
            except ValueError:
                return Response(
                    {"detail": "Invalid date. Use YYYY-MM-DD."},
                    status=400,
                )
        else:
            attendance_date = date.today()

        records = request.data.get("attendance")

        if not isinstance(records, list):
            return Response(
                {"detail": "attendance must be a list."},
                status=400,
            )

        valid_statuses = {
            "PRESENT",
            "ABSENT",
            "LATE",
            "EXCUSED",
        }

        enrollments = {
            enrollment.student_id: enrollment
            for enrollment in Enrollment.objects.filter(
                class_level=assigned_class,
                term=current_term,
            )
        }

        saved = 0

        for item in records:
            if not isinstance(item, dict):
                continue

            student_id = item.get("student_id")
            status = str(
                item.get("status", "PRESENT")
            ).upper()

            try:
                student_id = int(student_id)
            except (TypeError, ValueError):
                continue

            if status not in valid_statuses:
                continue

            enrollment = enrollments.get(student_id)

            if enrollment is None:
                continue

            Attendance.objects.update_or_create(
                student_id=student_id,
                date=attendance_date,
                defaults={
                    "enrollment": enrollment,
                    "status": status,
                    "marked_by": teacher,
                },
            )

            saved += 1

        return Response({
            "success": True,
            "date": attendance_date.isoformat(),
            "class": assigned_class.name,
            "saved": saved,
        })
