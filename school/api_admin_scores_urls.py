from django.urls import path

from .api_admin_scores import AdminScoresAPIView


urlpatterns = [
    path(
        "scores/",
        AdminScoresAPIView.as_view(),
        name="api_admin_scores",
    ),
]
