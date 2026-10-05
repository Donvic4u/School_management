from django.urls import path

from .api_teacher_results import TeacherStudentResultAPIView


urlpatterns = [
    path(
        "students/<int:student_id>/result/",
        TeacherStudentResultAPIView.as_view(),
        name="api_teacher_student_result",
    ),
]
