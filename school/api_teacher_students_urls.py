from django.urls import path

from .api_teacher_students import TeacherStudentsAPIView
from .api_teacher_student_update import TeacherStudentUpdateAPIView
from .api_teacher_student_add import TeacherStudentAddAPIView

urlpatterns = [
    path(
        "students/",
        TeacherStudentsAPIView.as_view(),
        name="teacher_students_api",
    ),
    path(
        "students/<int:student_id>/update/",
        TeacherStudentUpdateAPIView.as_view(),
        name="teacher_student_update_api",
    ),
    path(
        "students/add/",
        TeacherStudentAddAPIView.as_view(),
        name="teacher_student_add_api",
    ),
]
