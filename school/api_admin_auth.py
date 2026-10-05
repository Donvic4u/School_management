from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView


class AdminLoginAPIView(APIView):
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

        if not user.is_staff:
            return Response(
                {
                    "success": False,
                    "message": "Administrator access is required.",
                },
                status=403,
            )

        token, created = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "Administrator login successful.",
                "token": token.key,
                "administrator": {
                    "username": user.username,
                    "name": user.get_full_name() or user.username,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                },
            }
        )
