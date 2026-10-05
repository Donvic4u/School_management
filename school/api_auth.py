from django.contrib.auth import authenticate

from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView


class TeacherLoginAPIView(APIView):
    """
    API login for the native Android teacher application.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))

        if not username or not password:
            return Response(
                {
                    "success": False,
                    "message": "Username and password are required.",
                },
                status=400,
            )

        user = authenticate(
            username=username,
            password=password,
        )

        if user is None:
            return Response(
                {
                    "success": False,
                    "message": "Invalid username or password.",
                },
                status=401,
            )

        if not user.is_active:
            return Response(
                {
                    "success": False,
                    "message": "This account is inactive.",
                },
                status=403,
            )

        try:
            account = user.teacher_account
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

        token, created = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "Login successful.",
                "token": token.key,
                "teacher": {
                    "staff_id": account.teacher.staff_id,
                    "name": account.teacher.full_name,
                    "username": user.username,
                },
            }
        )
