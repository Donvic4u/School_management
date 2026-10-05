from django.urls import path

from .api_auth import TeacherLoginAPIView


urlpatterns = [
    path(
        "teacher/login/",
        TeacherLoginAPIView.as_view(),
        name="api_teacher_login",
    ),
]
