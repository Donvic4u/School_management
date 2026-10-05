from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Enrollment,
    ResultPublication,
    SchoolProfile,
)
from .result_views import build_class_results
from .views import get_current_term


class TeacherStudentResultAPIView(APIView):
    """
    Return the official published result for a student belonging
    to the authenticated teacher's Form Teacher class.

    Uses the existing build_class_results() calculation so the
    Android app and web/PDF results use the same result logic.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):

        # ---------------------------------------------------------
        # Verify teacher account
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Teacher must have exactly one Form Teacher class
        # ---------------------------------------------------------
        from .models import ClassLevel

        assigned_classes = list(
            ClassLevel.objects.filter(
                form_teacher=teacher
            ).order_by("name")
        )

        if not assigned_classes:
            return Response(
                {
                    "success": False,
                    "message": "No Form Teacher class is currently assigned.",
                },
                status=403,
            )

        if len(assigned_classes) > 1:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Your account is assigned to more than one "
                        "Form Teacher class."
                    ),
                },
                status=409,
            )

        assigned_class = assigned_classes[0]

        # ---------------------------------------------------------
        # Current term
        # ---------------------------------------------------------
        term = get_current_term()

        if term is None:
            return Response(
                {
                    "success": False,
                    "message": "No current academic term has been configured.",
                },
                status=409,
            )

        # ---------------------------------------------------------
        # Student must belong to teacher's assigned class
        # ---------------------------------------------------------
        enrollment = (
            Enrollment.objects
            .filter(
                student_id=student_id,
                class_level=assigned_class,
                term=term,
            )
            .select_related(
                "student",
                "class_level",
                "term",
                "term__session",
            )
            .first()
        )

        if enrollment is None:
            return Response(
                {
                    "success": False,
                    "message": "Student not found in your assigned class.",
                },
                status=404,
            )

        # ---------------------------------------------------------
        # Result must have been officially published
        # ---------------------------------------------------------
        publication = (
            ResultPublication.objects
            .filter(
                session=term.session,
                term=term,
                class_level=assigned_class,
                published=True,
            )
            .first()
        )

        if publication is None:
            return Response(
                {
                    "success": False,
                    "message": "This result has not been published yet.",
                },
                status=403,
            )

        # ---------------------------------------------------------
        # Use the EXISTING official result calculation
        # ---------------------------------------------------------
        class_results = build_class_results(
            assigned_class,
            term,
        )

        student_data = next(
            (
                item
                for item in class_results["students"]
                if item["student"].id == enrollment.student.id
            ),
            None,
        )

        if student_data is None:
            return Response(
                {
                    "success": False,
                    "message": "No result data was found for this student.",
                },
                status=404,
            )

        # ---------------------------------------------------------
        # Subject results
        # ---------------------------------------------------------
        subjects = []

        for item in student_data.get("subjects", []):

            subject = item["subject"]

            def decimal_value(value):
                if value is None:
                    return None
                return float(value)

            subjects.append(
                {
                    "code": subject["subject__code"],
                    "name": subject["subject__name"],
                    "ca1": decimal_value(item["ca1"]),
                    "ca2": decimal_value(item["ca2"]),
                    "ca3": decimal_value(item["ca3"]),
                    "exam": decimal_value(item["exam"]),
                    "total": decimal_value(item["total"]),
                    "grade": item["grade"],
                    "remark": item["remark"],
                    "position": item["position"],
                    "approved": item["approved"],
                }
            )

        # ---------------------------------------------------------
        # Existing remark mappings
        # ---------------------------------------------------------
        form_teacher_remark = dict(
            Enrollment.FORM_TEACHER_COMMENT_CHOICES
        ).get(
            enrollment.form_teacher_comment,
            enrollment.form_teacher_comment or "",
        )

        principal_remark = dict(
            Enrollment.ACADEMIC_PERFORMANCE_COMMENT_CHOICES
        ).get(
            enrollment.academic_performance_comment,
            enrollment.academic_performance_comment or "",
        )

        # ---------------------------------------------------------
        # Existing result reference format
        # ---------------------------------------------------------
        session_code = str(
            term.session.name
        ).replace("/", "")

        term_code = (
            str(term.name)
            .strip()
            .upper()
            .replace(" ", "")[:3]
        )

        result_reference = (
            f"{enrollment.student.admission_number}-"
            f"{session_code}-"
            f"{term_code}"
        )

        school = SchoolProfile.objects.first()

        return Response(
            {
                "success": True,

                "school": {
                    "name": school.name if school else "",
                    "address": school.address if school else "",
                    "phone": school.phone if school else "",
                    "email": school.email if school else "",
                    "motto": school.motto if school else "",
                },

                "student": {
                    "id": enrollment.student.id,
                    "admission_number": enrollment.student.admission_number,
                    "name": enrollment.student.full_name,
                    "gender": enrollment.student.gender,
                    "date_of_birth": (
                        enrollment.student.date_of_birth.isoformat()
                        if enrollment.student.date_of_birth
                        else None
                    ),
                    "class": assigned_class.name,
                },

                "session": term.session.name,
                "term": term.name,

                "result_reference": result_reference,

                "subjects": subjects,

                "summary": {
                    "total_marks": float(
                        student_data.get("total_marks", 0)
                    ),
                    "average": float(
                        student_data.get("average", 0)
                    ),
                    "overall_grade": student_data.get(
                        "overall_grade",
                        "",
                    ),
                    "overall_remark": student_data.get(
                        "overall_remark",
                        "",
                    ),
                    "position": student_data.get(
                        "position",
                        "",
                    ),
                    "completed_subjects": student_data.get(
                        "completed_subjects",
                        0,
                    ),
                    "total_subjects": student_data.get(
                        "total_subjects",
                        0,
                    ),
                    "complete": student_data.get(
                        "complete",
                        False,
                    ),
                },

                "form_teacher_remark": form_teacher_remark,
                "principal_remark": principal_remark,
            }
        )
