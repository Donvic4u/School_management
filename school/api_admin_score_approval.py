from django.contrib import admin
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Score


class AdminScoreApprovalAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response(
                {
                    "success": False,
                    "message": "Administrator access is required.",
                },
                status=403,
            )

        score_id = request.data.get("score_id")

        if not score_id:
            return Response(
                {
                    "success": False,
                    "message": "score_id is required.",
                },
                status=400,
            )

        try:
            score = (
                Score.objects
                .select_related(
                    "enrollment__student",
                    "enrollment__class_level",
                    "enrollment__term__session",
                    "subject",
                )
                .get(id=score_id)
            )
        except Score.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Score not found.",
                },
                status=404,
            )

        if not score.submitted:
            return Response(
                {
                    "success": False,
                    "message": "Only submitted scores can be approved.",
                },
                status=409,
            )

        if score.approved:
            return Response(
                {
                    "success": False,
                    "message": "This score has already been approved and locked.",
                },
                status=409,
            )

        score.approved = True
        score.save(update_fields=["approved"])

        return Response(
            {
                "success": True,
                "message": "Score approved and locked.",
                "score": {
                    "id": score.id,
                    "student": {
                        "id": score.enrollment.student.id,
                        "name": score.enrollment.student.full_name,
                        "admission_number": score.enrollment.student.admission_number,
                    },
                    "class": score.enrollment.class_level.name,
                    "session": score.enrollment.term.session.name,
                    "term": score.enrollment.term.name,
                    "subject": {
                        "id": score.subject.id,
                        "code": score.subject.code,
                        "name": score.subject.name,
                    },
                    "submitted": score.submitted,
                    "approved": score.approved,
                },
            }
        )
