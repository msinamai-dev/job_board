from django.urls import path
from . import views

app_name = "job_boardApp"

urlpatterns = [
    # Public
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_choice, name="register_choice"),
    path("register/employer/", views.register_employer, name="register_employer"),
    path("register/seeker/", views.register_seeker, name="register_seeker"),
    path("jobs/<int:job_id>/", views.job_detail, name="job_detail"),

    # Employer side
    path("employer/", views.employer_dashboard, name="employer_dashboard"),
    path("employer/audits/", views.audit_history, name="audit_history"),
    path("employer/analytics/", views.employer_analytics, name="employer_analytics"),
    path("employer/post-job/", views.post_job, name="post_job"),
    path("employer/jobs/<int:job_id>/close/", views.close_job, name="close_job"),
    path("employer/jobs/<int:job_id>/candidates/", views.job_candidates, name="job_candidates"),
    path("employer/candidates/<int:seeker_id>/", views.candidate_detail, name="candidate_detail"),
    path("employer/matches/<int:match_id>/invite/", views.send_interview_invite, name="send_interview_invite"),

    # Employee / job seeker side
    path("dashboard/", views.employee_dashboard, name="employee_dashboard"),
    path("matches/<int:match_id>/dismiss/", views.dismiss_match, name="dismiss_match"),
    path("analytics/", views.seeker_analytics, name="seeker_analytics"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("invites/<int:invite_id>/feedback/", views.submit_feedback, name="submit_feedback"),
    path("invites/<int:invite_id>/<str:action>/", views.respond_to_invite, name="respond_to_invite"),

    # Notifications API (used by JS polling)
    path("api/notifications/", views.get_notifications, name="get_notifications"),
    path("api/notifications/<int:notification_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("api/notifications/read-all/", views.mark_all_read, name="mark_all_read"),
]
