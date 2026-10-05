from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Score


class AdminScoresAPIView(APIView):
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

        scores = (
            Score.objects
            .select_related(
                "enrollment__student",
                "enrollment__class_level",
                "enrollment__term__session",
                "subject",
            )
            .order_by(
                "enrollment__class_level__name",
                "subject__name",
                "enrollment__student__surname",
                "enrollment__student__first_name",
            )
        )

        # Optional filters
        class_name = request.query_params.get("class")
        session_name = request.query_params.get("session")
        term_name = request.query_params.get("term")
        subject_id = request.query_params.get("subject_id")
        status_filter = request.query_params.get("status")

        if class_name:
            scores = scores.filter(
                enrollment__class_level__name=class_name
            )

        if session_name:
            scores = scores.filter(
                enrollment__term__session__name=session_name
            )

        if term_name:
            scores = scores.filter(
                enrollment__term__name=term_name
            )

        if subject_id:
            try:
                scores = scores.filter(subject_id=int(subject_id))
            except (TypeError, ValueError):
                return Response(
                    {
                        "success": False,
                        "message": "Invalid subject_id.",
                    },
                    status=400,
                )

        if status_filter:
            status_filter = status_filter.lower().strip()

            if status_filter == "pending":
                scores = scores.filter(
                    submitted=True,
                    approved=False,
                )

            elif status_filter == "approved":
                scores = scores.filter(
                    approved=True,
                )

            elif status_filter == "submitted":
                scores = scores.filter(
                    submitted=True,
                )

            elif status_filter == "draft":
                scores = scores.filter(
                    submitted=False,
                    approved=False,
                )

            elif status_filter != "all":
                return Response(
                    {
                        "success": False,
                        "message": (
                            "Invalid status. Use: all, pending, "
                            "approved, submitted or draft."
                        ),
                    },
                    status=400,
                )

        data = []

        for score in scores:
            data.append(
                {
                    "id": score.id,
                    "student": {
                        "id": score.enrollment.student.id,
                        "name": score.enrollment.student.full_name,
                        "admission_number": (
                            score.enrollment.student.admission_number
                        ),
                    },
                    "class": score.enrollment.class_level.name,
                    "session": score.enrollment.term.session.name,
                    "term": score.enrollment.term.name,
                    "subject": {
                        "id": score.subject.id,
                        "code": score.subject.code,
                        "name": score.subject.name,
                    },
                    "score": {
                        "ca1": (
                            float(score.ca1_score)
                            if score.ca1_score is not None
                            else None
                        ),
                        "ca2": (
                            float(score.ca2_score)
                            if score.ca2_score is not None
                            else None
                        ),
                        "ca3": (
                            float(score.ca3_score)
                            if score.ca3_score is not None
                            else None
                        ),
                        "exam": (
                            float(score.exam_score)
                            if score.exam_score is not None
                            else None
                        ),
                        "total": float(score.total),
                    },
                    "submitted": score.submitted,
                    "approved": score.approved,
                }
            )

        return Response(
            {
                "success": True,
                "count": len(data),
                "filters": {
                    "class": class_name or "",
                    "session": session_name or "",
                    "term": term_name or "",
                    "subject_id": subject_id or "",
                    "status": status_filter or "all",
                },
                "scores": data,
            }
        )
