from django.urls import path

from .api_admin_auth import AdminLoginAPIView


urlpatterns = [
    path(
        "login/",
        AdminLoginAPIView.as_view(),
        name="api_admin_login",
    ),
]
