from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from job_boardApp.models import Job, InterviewInvite, JobAudit
from job_boardApp.archiving import archive_and_delete_job


def _invite_datetime(invite):
    """Combine an invite's date and time into one comparable datetime,
    made timezone-aware if the project uses timezone-aware datetimes
    (the Django default). Falls back to a naive datetime if aware
    conversion isn't possible (e.g. an ambiguous DST moment) — still
    good enough for a same-day comparison."""
    naive = datetime.combine(invite.interview_date, invite.interview_time)
    if timezone.is_naive(naive):
        try:
            return timezone.make_aware(naive)
        except Exception:
            return naive
    return naive


class Command(BaseCommand):
    help = (
        "Finds every job whose latest scheduled interview date+time has "
        "already passed (checked to the minute, not just the day), "
        "writes a permanent snapshot to JobAudit, then permanently "
        "deletes the Job — cascading away its JobMatch and "
        "InterviewInvite rows (that data is preserved in the audit "
        "instead). Jobs with no interview invites at all are left "
        "untouched — those are only removed by an employer manually "
        "closing them (see views.close_job). Run this frequently "
        "(e.g. every 10-15 minutes) via a repeating scheduled task for "
        "near-real-time archiving — see README.md."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        archived_count = 0

        job_ids_with_invites = (
            InterviewInvite.objects.values_list("match__job_id", flat=True).distinct()
        )

        for job in Job.objects.filter(id__in=job_ids_with_invites):
            invites = list(
                InterviewInvite.objects.filter(match__job=job).select_related("job_seeker")
            )
            if not invites:
                continue

            latest_invite = max(
                invites,
                key=lambda i: _invite_datetime(i),
            )
            latest_dt = _invite_datetime(latest_invite)

            if latest_dt >= now:
                continue  # interview(s) still upcoming — leave this job alone

            job_title_for_log = job.title
            audit = archive_and_delete_job(job, reason=JobAudit.REASON_INTERVIEW_PASSED)
            archived_count += 1

            self.stdout.write(
                f"Archived and removed '{job_title_for_log}' "
                f"(interview was {audit.interview_date} {audit.interview_time}, "
                f"{audit.attendees or 'no'} attendee(s))."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Archived and removed {archived_count} completed job(s)."
            )
        )
