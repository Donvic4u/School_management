from django.urls import path

from .api_teacher import TeacherProfileAPIView


urlpatterns = [
    path(
        "profile/",
        TeacherProfileAPIView.as_view(),
        name="api_teacher_profile",
    ),
]
