from django.urls import path

from .api_teacher_score_submit_all import TeacherSubmitAllScoresAPIView


urlpatterns = [
    path(
        "score-entry/submit-all/",
        TeacherSubmitAllScoresAPIView.as_view(),
        name="api_teacher_score_submit_all",
    ),
]
