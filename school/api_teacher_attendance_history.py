from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Attendance, ClassLevel, Enrollment, Term, TeacherAccount


class TeacherAttendanceHistoryAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_teacher(self, request):
        try:
            return TeacherAccount.objects.select_related("teacher").get(
                user=request.user
            )
        except TeacherAccount.DoesNotExist:
            return None

    def get(self, request):
        teacher = self.get_teacher(request)

        if teacher is None:
            return Response(
                {"detail": "Teacher account not found."},
                status=403,
            )

        assigned_classes = list(
            ClassLevel.objects
            .filter(form_teacher=teacher.teacher)
            .order_by("name")
        )

        if not assigned_classes:
            return Response(
                {"detail": "No form class is assigned to this teacher."},
                status=400,
            )

        if len(assigned_classes) > 1:
            return Response(
                {"detail": "More than one form class is assigned to this teacher."},
                status=400,
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
                {"detail": "No current academic term is configured."},
                status=400,
            )

        student_id = request.query_params.get("student_id")

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

        if student_id:
            try:
                student_id = int(student_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Invalid student_id."},
                    status=400,
                )

            enrollments = enrollments.filter(student_id=student_id)

        enrollment_ids = list(
            enrollments.values_list("id", flat=True)
        )

        records = (
            Attendance.objects
            .filter(enrollment_id__in=enrollment_ids)
            .select_related("student", "enrollment")
            .order_by(
                "-date",
                "student__surname",
                "student__first_name",
            )
        )

        students = {}

        for enrollment in enrollments:
            student = enrollment.student

            students[student.id] = {
                "student_id": student.id,
                "admission_number": student.admission_number,
                "full_name": student.full_name,
                "records": [],
                "present": 0,
                "absent": 0,
                "late": 0,
                "excused": 0,
            }

        for record in records:
            student_data = students.get(record.student_id)

            if student_data is None:
                continue

            status = record.status.upper()

            student_data["records"].append({
                "date": record.date.isoformat(),
                "status": status,
            })

            if status == "PRESENT":
                student_data["present"] += 1
            elif status == "ABSENT":
                student_data["absent"] += 1
            elif status == "LATE":
                student_data["late"] += 1
            elif status == "EXCUSED":
                student_data["excused"] += 1

        for student_data in students.values():
            total = (
                student_data["present"]
                + student_data["absent"]
                + student_data["late"]
                + student_data["excused"]
            )

            student_data["total_marked"] = total

            if total > 0:
                student_data["attendance_rate"] = round(
                    (
                        student_data["present"]
                        + student_data["late"]
                    )
                    / total
                    * 100,
                    1,
                )
            else:
                student_data["attendance_rate"] = 0

        return Response({
            "class": assigned_class.name,
            "term": current_term.name,
            "session": current_term.session.name,
            "students": list(students.values()),
        })
