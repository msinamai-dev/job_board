from datetime import date
import os

from django.db import models
from django.contrib.auth.models import User


class Employer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employer_profile")
    company_name = models.CharField(max_length=255)
    company_bio = models.TextField(blank=True)
    location = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.company_name


class JobSeeker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seeker_profile")
    full_name = models.CharField(max_length=255)
    jtitle = models.CharField(max_length=255, blank=True, help_text="Your job title / role, e.g. 'IT Assistant'")
    skills = models.TextField(help_text="Comma-separated skills e.g. Python, Django, SQL")
    location = models.CharField(max_length=150)
    experience_years = models.PositiveIntegerField(default=0)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)
    esco_skills_cache = models.TextField(blank=True, default="")
    cv = models.FileField(upload_to="cvs/%Y/%m/", blank=True, null=True)
    cv_text_cache = models.TextField(blank=True, default="")

    def __str__(self):
        return self.full_name

    @property
    def age(self):
        """Age in whole years, calculated from date_of_birth."""
        if not self.date_of_birth:
            return None
        today = date.today()
        had_birthday = (today.month, today.day) >= (self.date_of_birth.month, self.date_of_birth.day)
        return today.year - self.date_of_birth.year - (0 if had_birthday else 1)
    
    @property
    def cv_ext(self):
        return os.path.splitext(self.cv.name)[1].lower() if self.cv else ""


class Job(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=255)
    description = models.TextField()
    required_skills = models.TextField(help_text="Comma-separated skills e.g. Python, Django, SQL")
    location = models.CharField(max_length=150)
    min_experience = models.PositiveIntegerField(default=0)
    salary = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    esco_skills_cache = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.title} @ {self.employer.company_name}"


class JobMatch(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="matches")
    job_seeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="matches")
    score = models.FloatField()
    matched_at = models.DateTimeField(auto_now_add=True)
    dismissed_by_seeker = models.BooleanField(default=False)

    class Meta:
        unique_together = ("job", "job_seeker")
        ordering = ["-score"]

    def __str__(self):
        return f"{self.job_seeker} <-> {self.job} ({self.score})"


class InterviewInvite(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES = [ 
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
    ]

    match = models.ForeignKey(JobMatch, on_delete=models.CASCADE, related_name="invites")
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="sent_invites")
    job_seeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="received_invites")
    interview_date = models.DateField()
    interview_time = models.TimeField()
    venue = models.CharField(max_length=255)
    note = models.TextField(blank=True, help_text="Optional extra instructions for the candidate")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    # Set True once the day-before reminder has gone out, so the
    # scheduled command never sends it twice for the same invite.
    reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Interview: {self.job_seeker} for {self.match.job.title} ({self.status})"


class JobAudit(models.Model):
    """A permanent, standalone record of a completed job posting — kept
    even after the Job itself (and its matches/invites) is deleted once
    its interview date has passed. Fields are plain snapshots (not
    foreign keys) on purpose: the Employer/JobSeeker/Job rows this
    refers to may no longer exist by the time someone reads this audit,
    so everything needed to understand what happened is copied in here
    directly rather than referenced."""

    # --- Snapshot of the job advert ---
    job_title = models.CharField(max_length=255)
    job_description = models.TextField(blank=True)
    required_skills = models.TextField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    min_experience = models.PositiveIntegerField(default=0)
    salary = models.CharField(max_length=100, blank=True)
    employer_name = models.CharField(max_length=255, blank=True)
    employer_username = models.CharField(max_length=150, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    # --- Interview outcome summary ---
    # Nullable because an employer can manually close a vacancy before
    # anyone was ever invited to interview — there's no date to record.
    interview_date = models.DateField(null=True, blank=True, help_text="The latest interview date associated with this job, if any")
    interview_time = models.TimeField(null=True, blank=True, help_text="Time of that latest interview, if any")
    attendees = models.TextField(
        blank=True,
        help_text="Comma-separated names of candidates who accepted their invite (treated as attending)",
    )
    total_invites_sent = models.PositiveIntegerField(default=0)
    total_accepted = models.PositiveIntegerField(default=0)
    total_declined = models.PositiveIntegerField(default=0)
    total_no_response = models.PositiveIntegerField(default=0)

    # --- Match & feedback aggregates (captured before JobMatch/Feedback
    # cascade-delete along with the Job, so this data survives that) ---
    total_matches = models.PositiveIntegerField(default=0)
    avg_match_score = models.FloatField(default=0, help_text="Stored as a percentage (0-100)")
    feedback_count = models.PositiveIntegerField(default=0)
    avg_feedback_rating = models.FloatField(default=0, help_text="1-5 scale, both sides combined")
    employer_feedback_count = models.PositiveIntegerField(default=0)
    employer_avg_rating = models.FloatField(default=0)
    seeker_feedback_count = models.PositiveIntegerField(default=0)
    seeker_avg_rating = models.FloatField(default=0)
    feedback_summary = models.TextField(blank=True, help_text="Freeform comments left by either side, newline-separated")

    REASON_INTERVIEW_PASSED = "interview_passed"
    REASON_MANUAL_CLOSE = "manual_close"
    REASON_CHOICES = [
        (REASON_INTERVIEW_PASSED, "Interview date passed (auto-archived)"),
        (REASON_MANUAL_CLOSE, "Closed manually by employer"),
    ]
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_INTERVIEW_PASSED)

    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-archived_at"]

    def __str__(self):
        return f"Audit: {self.job_title} (interview {self.interview_date})"


class SeekerAudit(models.Model):
    """Per-seeker snapshot captured at the same moment as its parent
    JobAudit. JobAudit only stores job-wide totals (total_matches,
    avg_match_score, etc.) — it has no way to say which specific
    seekers were involved. Without this, seeker-side analytics would
    lose all history the moment a job (and its JobMatch/InterviewInvite
    rows) gets cascade-deleted. One row per seeker who had a match on
    the job being archived."""

    job_audit = models.ForeignKey(JobAudit, on_delete=models.CASCADE, related_name="seeker_entries")
    seeker_username = models.CharField(max_length=150)
    seeker_full_name = models.CharField(max_length=255, blank=True)
    match_score = models.FloatField(null=True, blank=True, help_text="0.0-1.0, same scale as JobMatch.score")
    invite_status = models.CharField(
        max_length=10, blank=True,
        help_text="'', pending, accepted, or declined — blank means no invite was ever sent to this seeker",
    )
    feedback_rating_given = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="The rating this seeker gave for the interview, if any",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.seeker_full_name} — {self.job_audit.job_title}"


class Feedback(models.Model):
    """Captures user satisfaction after an interview — from either side.
    This is the raw data behind the 'feedback loop' objective: it's
    aggregated in the analytics views so both sides (and, informally,
    whoever tunes matching.py) can see whether high-scoring matches are
    actually translating into good real-world outcomes."""

    ROLE_EMPLOYER = "employer"
    ROLE_SEEKER = "seeker"
    ROLE_CHOICES = [
        (ROLE_EMPLOYER, "Employer"),
        (ROLE_SEEKER, "Job Seeker"),
    ]

    invite = models.ForeignKey(InterviewInvite, on_delete=models.CASCADE, related_name="feedback_entries")
    submitted_by_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    submitted_by_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedback_submitted")
    rating = models.PositiveSmallIntegerField(help_text="1 (poor) to 5 (excellent)")
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # One feedback entry per person per invite — they can edit it,
        # not spam multiple ratings for the same interview.
        unique_together = ("invite", "submitted_by_user")

    def __str__(self):
        return f"{self.submitted_by_role} feedback: {self.rating}/5 for invite #{self.invite_id}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
