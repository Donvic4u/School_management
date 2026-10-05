from django.urls import path

from .api_admin_student_update import AdminStudentUpdateAPIView


urlpatterns = [
    path(
        "students/<int:student_id>/",
        AdminStudentUpdateAPIView.as_view(),
        name="api_admin_student_update",
    ),
]
