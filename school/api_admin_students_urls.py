from django.urls import path

from .api_admin_students import AdminStudentsAPIView


urlpatterns = [
    path(
        "students/",
        AdminStudentsAPIView.as_view(),
        name="api_admin_students",
    ),
]
