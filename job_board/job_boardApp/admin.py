from django.contrib import admin
from .models import Employer, JobSeeker, Job, JobMatch, InterviewInvite, JobAudit, SeekerAudit, Feedback, Notification

admin.site.register(Employer)
admin.site.register(JobSeeker)
admin.site.register(Job)
admin.site.register(JobMatch)
admin.site.register(InterviewInvite)
admin.site.register(Feedback)
admin.site.register(Notification)


class SeekerAuditInline(admin.TabularInline):
    model = SeekerAudit
    extra = 0
    readonly_fields = [f.name for f in SeekerAudit._meta.fields]
    can_delete = False


@admin.register(JobAudit)
class JobAuditAdmin(admin.ModelAdmin):
    list_display = (
        "job_title", "employer_name", "reason", "interview_date",
        "total_matches", "total_invites_sent", "total_accepted", "total_declined",
        "total_no_response", "avg_match_score", "avg_feedback_rating", "archived_at",
    )
    list_filter = ("reason", "interview_date", "archived_at")
    search_fields = ("job_title", "employer_name", "employer_username", "attendees")
    readonly_fields = [f.name for f in JobAudit._meta.fields]
    inlines = [SeekerAuditInline]
