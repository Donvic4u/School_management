from django.urls import path

from .api_teacher_attendance import TeacherAttendanceAPIView


urlpatterns = [
    path(
        "attendance/",
        TeacherAttendanceAPIView.as_view(),
        name="api_teacher_attendance",
    ),
]
