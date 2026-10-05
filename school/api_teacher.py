from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassLevel


class TeacherProfileAPIView(APIView):
    """
    Return the authenticated teacher's profile and assigned Form Teacher class.
    """

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
            ClassLevel.objects
            .filter(form_teacher=teacher)
            .order_by("name")
            .values_list("name", flat=True)
        )

        return Response(
            {
                "success": True,
                "teacher": {
                    "staff_id": teacher.staff_id,
                    "name": teacher.full_name,
                    "username": request.user.username,
                    "email": teacher.email,
                    "phone": teacher.phone,
                    "form_teacher_classes": assigned_classes,
                },
            }
        )
