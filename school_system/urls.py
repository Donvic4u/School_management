from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("school.urls")),
    path("api/", include("school.api_urls")),
    path("api/auth/", include("school.api_auth_urls")),
    path("api/admin-auth/", include("school.api_admin_auth_urls")),
    path("api/teacher/", include("school.api_teacher_urls")),
    path("api/teacher/", include("school.api_teacher_students_urls")),
    path("api/teacher/", include("school.api_teacher_results_urls")),
    path("api/teacher/", include("school.api_teacher_score_entry_urls")),
    path("api/teacher/", include("school.api_teacher_score_save_urls")),
    path("api/teacher/", include("school.api_teacher_score_submit_urls")),
    path("api/teacher/", include("school.api_teacher_score_submit_all_urls")),
    path("api/admin/", include("school.api_admin_scores_urls")),
    path("api/admin/", include("school.api_admin_score_approval_urls")),
    path("api/admin/", include("school.api_admin_students_urls")),
    path("api/admin/", include("school.api_admin_student_update_urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

