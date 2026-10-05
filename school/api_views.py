from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SchoolProfile


class SchoolProfileAPIView(APIView):
    """
    Read-only API endpoint for the Android application.
    """

    def get(self, request):
        profile = SchoolProfile.objects.first()

        if profile is None:
            return Response(
                {
                    "success": False,
                    "message": "School profile has not been configured.",
                },
                status=404,
            )

        return Response(
            {
                "success": True,
                "school": {
                    "name": profile.name,
                    "address": profile.address,
                    "phone": profile.phone,
                    "email": profile.email,
                    "motto": profile.motto,
                },
            }
        )
