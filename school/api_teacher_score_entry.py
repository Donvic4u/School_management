from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel, ClassSubject, Enrollment, Score, Term


class TeacherScoreEntryAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
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
                        "Form Teacher class. Please contact the administrator."
                    ),
                },
                status=409,
            )

        assigned_class = assigned_classes[0]

        current_term = (
            Term.objects.filter(is_current=True)
            .select_related("session")
            .order_by("-session_id", "-id")
            .first()
        )

        if current_term is None:
            return Response(
                {
                    "success": False,
                    "message": "No current academic term has been configured.",
                },
                status=409,
            )

        class_subjects = (
            ClassSubject.objects.filter(
                class_level=assigned_class,
                active=True,
            )
            .select_related("subject")
            .order_by("subject__name")
        )

        subjects = [
            {
                "id": item.subject.id,
                "code": item.subject.code,
                "name": item.subject.name,
            }
            for item in class_subjects
        ]

        subject_id = request.query_params.get("subject_id")

        response = {
            "success": True,
            "teacher": {
                "staff_id": teacher.staff_id,
                "name": teacher.full_name,
                "username": request.user.username,
            },
            "class": {
                "id": assigned_class.id,
                "name": assigned_class.name,
            },
            "session": {
                "id": current_term.session.id,
                "name": current_term.session.name,
            },
            "term": {
                "id": current_term.id,
                "name": current_term.name,
            },
            "subjects": subjects,
        }

        if not subject_id:
            response["students"] = []
            response["selected_subject"] = None
            return Response(response)

        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "Invalid subject ID.",
                },
                status=400,
            )

        class_subject = (
            ClassSubject.objects.filter(
                class_level=assigned_class,
                subject_id=subject_id,
                active=True,
            )
            .select_related("subject")
            .first()
        )

        if class_subject is None:
            return Response(
                {
                    "success": False,
                    "message": "This subject is not assigned to your class.",
                },
                status=403,
            )

        enrollments = (
            Enrollment.objects.filter(
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

        students = []

        for enrollment in enrollments:
            student = enrollment.student

            score = Score.objects.filter(
                enrollment=enrollment,
                subject=class_subject.subject,
            ).first()

            students.append(
                {
                    "id": student.id,
                    "enrollment_id": enrollment.id,
                    "admission_number": student.admission_number,
                    "full_name": student.full_name,
                    "gender": student.gender,
                    "score": {
                        "id": score.id if score else None,
                        "ca1": float(score.ca1_score) if score and score.ca1_score is not None else None,
                        "ca2": float(score.ca2_score) if score and score.ca2_score is not None else None,
                        "ca3": float(score.ca3_score) if score and score.ca3_score is not None else None,
                        "exam": float(score.exam_score) if score and score.exam_score is not None else None,
                        "submitted": score.submitted if score else False,
                        "approved": score.approved if score else False,
                    },
                }
            )

        response["selected_subject"] = {
            "id": class_subject.subject.id,
            "code": class_subject.subject.code,
            "name": class_subject.subject.name,
        }
        response["students"] = students

        return Response(response)
