from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .api_student_auth import get_authenticated_student
from .models import Enrollment, ResultPublication, SchoolProfile
from .result_views import build_class_results


class StudentDashboardAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        student = get_authenticated_student(request)

        if student is None:
            return Response(
                {
                    "success": False,
                    "message": "Student authentication required."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile = SchoolProfile.objects.first()

        # Get the student's most recent enrollment that has a published result.
        enrollments = (
            Enrollment.objects
            .filter(student=student)
            .select_related(
                "class_level",
                "term",
                "term__session",
            )
            .order_by(
                "-term__session__id",
                "-term__id",
            )
        )

        recent_result = None

        for enrollment in enrollments:
            publication_exists = ResultPublication.objects.filter(
                session=enrollment.term.session,
                term=enrollment.term,
                class_level=enrollment.class_level,
                published=True,
            ).exists()

            if not publication_exists:
                continue

            class_results = build_class_results(
                enrollment.class_level,
                enrollment.term,
            )

            student_result = next(
                (
                    item
                    for item in class_results["students"]
                    if item["student"].id == student.id
                ),
                None,
            )

            if student_result is not None:
                recent_result = {
                    "enrollment": enrollment,
                    "result": student_result,
                }
                break

        result_data = None

        if recent_result is not None:
            enrollment = recent_result["enrollment"]
            student_result = recent_result["result"]

            session_code = str(
                enrollment.term.session.name
            ).replace("/", "")

            term_code = str(
                enrollment.term.name
            ).strip().upper().replace(" ", "")[:3]

            result_reference = (
                f"{student.admission_number}-"
                f"{session_code}-"
                f"{term_code}"
            )

            result_data = {
                "session": enrollment.term.session.name,
                "term": enrollment.term.name,
                "class": enrollment.class_level.name,
                "result_reference": result_reference,
                "total_marks": student_result["total_marks"],
                "average": student_result["average"],
                "overall_position": student_result["position"],
                "overall_grade": student_result["overall_grade"],
                "overall_remark": student_result["overall_remark"],
                "completed_subjects": student_result["completed_subjects"],
                "total_subjects": student_result["total_subjects"],
                "form_teacher_remark": dict(
                    Enrollment.FORM_TEACHER_COMMENT_CHOICES
                ).get(
                    enrollment.form_teacher_comment,
                    enrollment.form_teacher_comment or "",
                ),
                "principal_remark": dict(
                    Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
                ).get(
                    enrollment.academic_performance_comment,
                    enrollment.academic_performance_comment or "",
                ),
            }

        return Response(
            {
                "success": True,

                "school": {
                    "name": profile.name if profile else "",
                    "address": profile.address if profile else "",
                    "phone": profile.phone if profile else "",
                    "email": profile.email if profile else "",
                    "motto": profile.motto if profile else "",
                },

                "student": {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "surname": student.surname,
                    "first_name": student.first_name,
                    "other_names": student.other_names,
                    "full_name": student.full_name,
                    "gender": student.gender,
                    "phone_number": student.phone_number,
                    "email": student.email,
                    "passport_photo": (
                        request.build_absolute_uri(student.passport_photo.url)
                        if student.passport_photo
                        else None
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
                    "current_class": (
                        student.current_class.name
                        if student.current_class
                        else ""
                    ),
                    "active": student.active,
                },

                "most_recent_result": result_data,
            }
        )
