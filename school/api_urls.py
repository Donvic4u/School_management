from django.urls import path

from .api_views import SchoolProfileAPIView


urlpatterns = [
    path(
        "school/",
        SchoolProfileAPIView.as_view(),
        name="api_school_profile",
    ),
]
