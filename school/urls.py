from django.urls import path
from . import views
from .api_teacher_comments import TeacherCommentsAPIView
from .api_teacher_attendance import TeacherAttendanceAPIView
from .api_teacher_attendance_history import TeacherAttendanceHistoryAPIView
from .result_views import class_master_result, student_result, result_dashboard
from .pdf_views import student_result_pdf
from .master_pdf_views import class_master_result_pdf
from .excel_views import class_master_result_excel
from .public_result_views import public_result_portal
from .public_result_pdf_views import public_result_pdf
from .api_student_auth import StudentLoginAPIView
from .api_student_admin import AdminStudentLoginSettingsAPIView
from .api_student_result import StudentResultAPIView
from .api_student_dashboard import StudentDashboardAPIView

urlpatterns = [
    path("api/teacher/comments/", TeacherCommentsAPIView.as_view(), name="teacher_comments_api"),
    path("api/teacher/attendance/", TeacherAttendanceAPIView.as_view(), name="teacher_attendance_api"),
    path("api/teacher/attendance/history/", TeacherAttendanceHistoryAPIView.as_view(), name="teacher_attendance_history_api"),
    path("api/auth/student/login/", StudentLoginAPIView.as_view(), name="student_login_api"),
    path("api/student/result/", StudentResultAPIView.as_view(), name="student_result_api"),
path("api/student/dashboard/", StudentDashboardAPIView.as_view(), name="student_dashboard_api"),
    path("api/admin/students/<int:student_id>/login-settings/", AdminStudentLoginSettingsAPIView.as_view(), name="admin_student_login_settings_api"),
    path("form-teacher-comments/<int:class_id>/", views.form_teacher_comments, name="form_teacher_comments"),
    path("form-teacher-comments/<int:class_id>/student/<int:student_id>/", views.form_teacher_student_comments, name="form_teacher_student_comments"),
    path("result-portal/", public_result_portal, name="public_result_portal"),
    path("result-portal/pdf/", public_result_pdf, name="public_result_pdf"),
    path("", views.dashboard, name="dashboard"),
    path("promotion/", views.student_promotion, name="student_promotion"),
    path(
        "academic-sessions/",
        views.academic_session_management,
        name="academic_session_management",
    ),

    path("enrollments/", views.enrollment_management, name="enrollment_management"),
    path("students/", views.student_list, name="student_list"),
    path("students/add/", views.student_add, name="student_add"),
    path(
        "students/<int:student_id>/",
        views.student_detail,
        name="student_detail",
    ),
    path(
        "students/<int:student_id>/edit/",
        views.student_edit,
        name="student_edit",
    ),

    path("teachers/", views.teacher_list, name="teacher_list"),
    path("teachers/add/", views.teacher_add, name="teacher_add"),
    path(
        "teachers/<int:teacher_id>/edit/",
        views.teacher_edit,
        name="teacher_edit",
    ),
    path(
        "teachers/<int:teacher_id>/account/",
        views.teacher_account_manage,
        name="teacher_account_manage",
    ),
    path(
        "teachers/<int:teacher_id>/form-class/",
        views.teacher_form_class_manage,
        name="teacher_form_class_manage",
    ),

    path("subjects/", views.subject_list, name="subject_list"),
    path("subjects/add/", views.subject_add, name="subject_add"),
    path(
        "subjects/<int:subject_id>/edit/",
        views.subject_edit,
        name="subject_edit",
    ),

    path("classes/", views.class_list, name="class_list"),
    path(
        "classes/<int:class_id>/teacher/",
        views.class_teacher_edit,
        name="class_teacher_edit",
    ),

    path("scores/", views.score_entry, name="score_entry"),

    path("results/", result_dashboard, name="result_dashboard"),

    path(
        "results/class/<int:class_id>/",
        class_master_result,
        name="class_master_result",
    ),
    path(
        "results/class/<int:class_id>/pdf/",
        class_master_result_pdf,
        name="class_master_result_pdf",
    ),
    path(
        "results/class/<int:class_id>/excel/",
        class_master_result_excel,
        name="class_master_result_excel",
    ),
    path(
        "results/student/<int:student_id>/",
        student_result,
        name="student_result",
    ),
    path(
        "results/student/<int:student_id>/pdf/",
        student_result_pdf,
        name="student_result_pdf",
    ),
    path(
        "results/student/<int:student_id>/email/",
        views.email_student_result,
        name="email_student_result",
    ),

    path(
        "teacher-login/",
        views.teacher_login,
        name="teacher_login",
    ),
    path(
        "teacher-dashboard/",
        views.teacher_dashboard,
        name="teacher_dashboard",
    ),
    path(
        "teacher-attendance/",
        views.teacher_attendance,
        name="teacher_attendance",
    ),
    path(
        "teacher-attendance/history/",
        views.teacher_attendance_history,
        name="teacher_attendance_history",
    ),
    path(
        "teacher/students/add/",
        views.teacher_add_student,
        name="teacher_add_student",
    ),
    path(
        "teacher-logout/",
        views.teacher_logout,
        name="teacher_logout",
    ),
    path(
        "teacher-scores/<int:assignment_id>/",
        views.teacher_score_entry,
        name="teacher_score_entry",
    ),
    path(
        "form-teacher-scores/<int:class_id>/",
        views.form_teacher_score_entry,
        name="form_teacher_score_entry",
    ),
    path(
        "form-teacher-scores/<int:class_id>/student/<int:student_id>/",
        views.form_teacher_student_scores,
        name="form_teacher_student_scores",
    ),
]
