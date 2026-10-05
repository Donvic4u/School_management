from django.urls import path

from .api_admin_score_approval import AdminScoreApprovalAPIView

urlpatterns = [
    path(
        "approve-score/",
        AdminScoreApprovalAPIView.as_view(),
        name="api_admin_approve_score",
    ),
]
