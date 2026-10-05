from django.urls import path

from .api_teacher_score_entry import TeacherScoreEntryAPIView


urlpatterns = [
    path(
        "score-entry/",
        TeacherScoreEntryAPIView.as_view(),
        name="api_teacher_score_entry",
    ),
]
