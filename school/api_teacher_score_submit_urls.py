from django.urls import path

from .api_teacher_score_submit import TeacherScoreSubmitAPIView


urlpatterns = [
    path(
        "score-entry/submit/",
        TeacherScoreSubmitAPIView.as_view(),
        name="api_teacher_score_submit",
    ),
]
