
from django.db.models import Avg

from .models import InterviewInvite, JobAudit, JobMatch, Feedback, SeekerAudit


def archive_and_delete_job(job, reason=JobAudit.REASON_INTERVIEW_PASSED):
    invites = list(
        InterviewInvite.objects.filter(match__job=job).select_related("job_seeker__user")
    )

    latest_invite = None
    if invites:
        latest_invite = max(
            invites,
            key=lambda i: (i.interview_date, i.interview_time),
        )

    accepted = [i for i in invites if i.status == InterviewInvite.STATUS_ACCEPTED]
    declined = [i for i in invites if i.status == InterviewInvite.STATUS_DECLINED]
    no_response = [i for i in invites if i.status == InterviewInvite.STATUS_PENDING]
    attendee_names = ", ".join(sorted({i.job_seeker.full_name for i in accepted}))
    matches = JobMatch.objects.filter(job=job).select_related("job_seeker__user")
    total_matches = matches.count()
    avg_match_score = matches.aggregate(avg=Avg("score"))["avg"] or 0
    feedback = Feedback.objects.filter(invite__match__job=job)
    feedback_count = feedback.count()
    avg_feedback_rating = feedback.aggregate(avg=Avg("rating"))["avg"] or 0
    employer_feedback = feedback.filter(submitted_by_role=Feedback.ROLE_EMPLOYER)
    seeker_feedback = feedback.filter(submitted_by_role=Feedback.ROLE_SEEKER)
    employer_feedback_count = employer_feedback.count()
    seeker_feedback_count = seeker_feedback.count()
    employer_avg_rating = employer_feedback.aggregate(avg=Avg("rating"))["avg"] or 0
    seeker_avg_rating = seeker_feedback.aggregate(avg=Avg("rating"))["avg"] or 0

    feedback_summary = "\n".join(
        f"[{f.submitted_by_role}] {f.rating}/5 - {f.comments}"
        for f in feedback
        if f.comments
    )

    audit = JobAudit.objects.create(
        job_title=job.title,
        job_description=job.description,
        required_skills=job.required_skills,
        location=job.location,
        min_experience=job.min_experience,
        salary=job.salary,
        employer_name=job.employer.company_name,
        employer_username=job.employer.user.username,
        posted_at=job.created_at,
        interview_date=latest_invite.interview_date if latest_invite else None,
        interview_time=latest_invite.interview_time if latest_invite else None,
        attendees=attendee_names,
        total_invites_sent=len(invites),
        total_accepted=len(accepted),
        total_declined=len(declined),
        total_no_response=len(no_response),
        total_matches=total_matches,
        avg_match_score=round(avg_match_score * 100, 2),
        feedback_count=feedback_count,
        avg_feedback_rating=round(avg_feedback_rating, 2),
        employer_feedback_count=employer_feedback_count,
        employer_avg_rating=round(employer_avg_rating, 2),
        seeker_feedback_count=seeker_feedback_count,
        seeker_avg_rating=round(seeker_avg_rating, 2),
        feedback_summary=feedback_summary,
        reason=reason,
    )

    latest_invite_by_seeker = {}
    for inv in invites:
        current = latest_invite_by_seeker.get(inv.job_seeker_id)
        if current is None or (inv.interview_date, inv.interview_time) > (current.interview_date, current.interview_time):
            latest_invite_by_seeker[inv.job_seeker_id] = inv

    seeker_rating_by_invite_id = {
        f.invite_id: f.rating for f in seeker_feedback
    }

    seeker_audit_rows = []
    for match in matches:
        seeker = match.job_seeker
        invite = latest_invite_by_seeker.get(seeker.id)
        seeker_audit_rows.append(SeekerAudit(
            job_audit=audit,
            seeker_username=seeker.user.username,
            seeker_full_name=seeker.full_name,
            match_score=match.score,
            invite_status=invite.status if invite else "",
            feedback_rating_given=seeker_rating_by_invite_id.get(invite.id) if invite else None,
        ))
    if seeker_audit_rows:
        SeekerAudit.objects.bulk_create(seeker_audit_rows)

    job.delete() 
    return audit
