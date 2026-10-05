from django.urls import path

from .api_teacher_score_save import TeacherScoreSaveAPIView


urlpatterns = [
    path(
        "score-entry/save/",
        TeacherScoreSaveAPIView.as_view(),
        name="api_teacher_score_save",
    ),
]
