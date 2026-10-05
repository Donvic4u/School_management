from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .api_student_auth import get_authenticated_student
from .models import Enrollment, ResultPublication, SchoolProfile
from .result_views import build_class_results


class StudentResultAPIView(APIView):
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

        enrollment = (
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
            .first()
        )

        if enrollment is None:
            return Response(
                {
                    "success": False,
                    "message": "No result record was found for this student."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        publication = ResultPublication.objects.filter(
            session=enrollment.term.session,
            term=enrollment.term,
            class_level=enrollment.class_level,
            published=True,
        ).first()

        if publication is None:
            return Response(
                {
                    "success": False,
                    "message": "This result has not been published yet."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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

        if student_result is None:
            return Response(
                {
                    "success": False,
                    "message": "Student result could not be found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

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

        return Response(
            {
                "success": True,
                "school": {
                    "name": (
                        SchoolProfile.objects.first().name
                        if SchoolProfile.objects.exists()
                        else ""
                    ),
                    "address": (
                        SchoolProfile.objects.first().address
                        if SchoolProfile.objects.exists()
                        else ""
                    ),
                    "phone": (
                        SchoolProfile.objects.first().phone
                        if SchoolProfile.objects.exists()
                        else ""
                    ),
                    "email": (
                        SchoolProfile.objects.first().email
                        if SchoolProfile.objects.exists()
                        else ""
                    ),
                    "motto": (
                        SchoolProfile.objects.first().motto
                        if SchoolProfile.objects.exists()
                        else ""
                    ),
                },
                "student": {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "name": student.full_name,
                    "gender": student.gender,
                    "class": enrollment.class_level.name,
                },
                "session": enrollment.term.session.name,
                "term": enrollment.term.name,
                "result_reference": result_reference,
                "subjects": [
                    {
                        "subject": item["subject"].get(
                            "subject__name",
                            item["subject"].get("subject__code", "")
                        ),
                        "subject_code": item["subject"].get(
                            "subject__code",
                            ""
                        ),
                        "ca1": item["ca1"],
                        "ca2": item["ca2"],
                        "ca3": item["ca3"],
                        "exam": item["exam"],
                        "total": item["total"],
                        "grade": item["grade"],
                        "remark": item["remark"],
                        "position": item["position"],
                        "approved": item["approved"],
                    }
                    for item in student_result["subjects"]
                ],
                "summary": {
                    "total_marks": student_result["total_marks"],
                    "average": student_result["average"],
                    "completed_subjects": student_result["completed_subjects"],
                    "total_subjects": student_result["total_subjects"],
                    "overall_position": student_result["position"],
                    "overall_grade": student_result["overall_grade"],
                    "overall_remark": student_result["overall_remark"],
                },
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
        )
