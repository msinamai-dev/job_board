from datetime import date
import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.utils import timezone

from django.db.models import Avg, Count, Q

from .models import Employer, JobSeeker, Job, JobMatch, InterviewInvite, JobAudit, SeekerAudit, Feedback, Notification
from .advice import generate_job_candidate_advice, MAX_INTERVIEW_SLOTS
from .archiving import archive_and_delete_job


DASHBOARD_MIN_SCORE = 0.5


def _redirect_for_role(user):
    """Send a logged-in user to the right dashboard based on their role.
    This is the core of the RBAC split: an Employer account and a
    JobSeeker account never land on the same page after login."""
    if Employer.objects.filter(user=user).exists():
        return redirect("job_boardApp:employer_dashboard")
    if JobSeeker.objects.filter(user=user).exists():
        return redirect("job_boardApp:employee_dashboard")
    return redirect("job_boardApp:home")



from django.contrib import messages
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .middleware import FORCE_KEY
from .validators import check_cv, check_dob, check_password as password_errors


def login_view(request):
    template = "job_boardApp/login.html"
    if request.user.is_authenticated:
        return _redirect_for_role(request.user)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, template, {"page_title": "Login"})

        login(request, user)

        if password_errors(password, user.username):
            request.session[FORCE_KEY] = True
            messages.warning(
                request,
                "Your password does not meet our security requirements. "
                "Please choose a new one to continue.",
            )
            return redirect("job_boardApp:change_password")

        return _redirect_for_role(user)

    return render(request, template, {"page_title": "Login"})


@login_required
def change_password(request):
    template = "job_boardApp/change_password.html"
    forced = bool(request.session.get(FORCE_KEY))
    ctx = {"page_title": "Change Password", "forced": forced}

    if request.method == "POST":
        current = request.POST.get("current_password", "")
        new = request.POST.get("new_password", "")
        confirm = request.POST.get("confirm_password", "")

        errors = []
        if not request.user.check_password(current):
            errors.append("Your current password is incorrect.")
        if new != confirm:
            errors.append("The new passwords do not match.")
        if new and new == current:
            errors.append("Your new password must be different from the old one.")
        errors += password_errors(new, request.user.username)

        if errors:
            for e in dict.fromkeys(errors):      
                messages.error(request, e)
            return render(request, template, ctx)

        request.user.set_password(new)
        request.user.save()
        update_session_auth_hash(request, request.user)   
        request.session.pop(FORCE_KEY, None)
        messages.success(request, "Password changed successfully.")
        return _redirect_for_role(request.user)

    return render(request, template, ctx)


def logout_view(request):
    logout(request)
    messages.success(request, "You've been logged out.")
    return redirect("job_boardApp:home")


def home(request):
    """Public landing page. Shows recent active jobs and lets visitors
    choose whether they're an employer or a job seeker."""

    active_jobs = Job.objects.filter(is_active=True).count()
    inactive_jobs = Job.objects.filter(is_active=False).count()

    context = {
        "page_title": "Job Board - Find Talent, Find Work",
        "job_count": active_jobs,
        "seeker_count": JobSeeker.objects.count(),
        "employer_count": Employer.objects.count(),
        "active_jobs": active_jobs,
        "inactive_jobs": inactive_jobs,
    }
    return render(request, "job_boardApp/home.html", context)

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render

from .models import Employer, JobSeeker
from .validators import (
    check_text, check_company, check_username, check_password,
    check_skills, check_experience,
)


def register_choice(request):
    """Landing page for signup: pick employer or job seeker."""
    return render(request, "job_boardApp/register_choice.html", {"page_title": "Join the Job Board"})

MIN_SEEKER_AGE = 17
MAX_SEEKER_AGE = 70

def register_employer(request):
    template = "job_boardApp/register_employer.html"
    ctx = {"page_title": "Employer Sign Up", "form_data": {}}

    if request.method == "POST":
        data = {k: request.POST.get(k, "").strip() for k in ("username", "company_name", "location")}
        password = request.POST.get("password", "")
        errors = (
            check_username(data["username"])
            + check_password(password, data["username"])
            + check_company(data["company_name"])
            + check_text(data["location"], "Location", required=False)
        )
        if errors:
            for e in errors:
                messages.error(request, e)
            ctx["form_data"] = data         
            return render(request, template, ctx)

        with transaction.atomic():          
            user = User.objects.create_user(username=data["username"], password=password)
            Employer.objects.create(
                user=user, company_name=data["company_name"], location=data["location"]
            )
        login(request, user)
        messages.success(request, "Employer account created. Post your first job!")
        return _redirect_for_role(user)

    return render(request, template, ctx)
import os
import mimetypes
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import JobSeeker, JobMatch


@login_required
@xframe_options_sameorigin
def view_cv(request, seeker_id):
    seeker = get_object_or_404(JobSeeker, pk=seeker_id)
    if not seeker.cv:
        raise Http404("No CV uploaded.")

    # The seeker can always view their own CV
    allowed = request.user == seeker.user

    # An employer can view it only if the seeker is matched to one of their jobs
    if not allowed:
        allowed = JobMatch.objects.filter(
            job_seeker=seeker,
            job__employer__user=request.user,
            dismissed_by_seeker=False,
        ).exists()

    if not allowed:
        raise Http404

    content_type = mimetypes.guess_type(seeker.cv.name)[0] or "application/octet-stream"
    can_inline = seeker.cv_ext in (".pdf", ".txt")
    disposition = "inline" if can_inline and not request.GET.get("download") else "attachment"

    response = FileResponse(seeker.cv.open("rb"), content_type=content_type)
    response["Content-Disposition"] = f'{disposition}; filename="{os.path.basename(seeker.cv.name)}"'
    return response

def register_seeker(request):
    template = "job_boardApp/register_seeker.html"
    
    ctx = {
        "page_title": "Job Seeker Sign Up",
        "form_data": {},
        "dob_max": years_ago(MIN_SEEKER_AGE).isoformat(),
    }
    if request.method == "POST":
        data = {k: request.POST.get(k, "").strip() for k in
                ("username", "full_name", "date_of_birth", "jtitle", "skills", "location", "experience_years")}
        password = request.POST.get("password", "")
        cv_file = request.FILES.get("cv") 
        years, exp_errors = check_experience(data["experience_years"])
        dob, dob_errors = check_dob(data["date_of_birth"])
        errors = (
            check_username(data["username"])
            + check_password(password, data["username"])
            + check_text(data["full_name"], "Full name")
            + dob_errors
            + check_text(data["jtitle"], "Job title", required=False)
            + check_skills(data["skills"])
            + check_text(data["location"], "Location")
            + exp_errors
            + check_cv(cv_file) 
        )
        if errors:
            for e in errors:
                messages.error(request, e)
            ctx["form_data"] = data
            return render(request, template, ctx)
        with transaction.atomic():
            user = User.objects.create_user(username=data["username"], password=password)
            JobSeeker.objects.create(
                user=user,
                full_name=data["full_name"],
                date_of_birth=dob,
                jtitle=data["jtitle"],
                skills=data["skills"],
                location=data["location"],
                experience_years=years,
                cv=cv_file,
            )
        login(request, user)
        messages.success(request, "Profile created. We'll match you with jobs automatically!")
        return _redirect_for_role(user)

    return render(request, template, ctx)

def years_ago(years):
    today = date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # Feb 29 -> Feb 28
        return today.replace(year=today.year - years, day=28)

ctx = {
    "page_title": "Job Seeker Sign Up",
    "form_data": {},
    "dob_max": years_ago(MIN_SEEKER_AGE).isoformat(),
}

@login_required
def employer_dashboard(request):
    employer = Employer.objects.filter(user=request.user).first()
    if employer is None:
        messages.error(request, "That page is only available to employer accounts.")
        return redirect("job_boardApp:home")

    jobs = Job.objects.filter(employer=employer).order_by("-created_at")
    matches = JobMatch.objects.filter(job__employer=employer).select_related("job", "job_seeker")

    context = {
        "page_title": "Employer Dashboard",
        "employer": employer,
        "jobs": jobs,
        "matches": matches,
        "job_count": jobs.count(),
        "match_count": matches.count(),
    }
    return render(request, "job_boardApp/employer_dashboard.html", context)


@login_required
def audit_history(request):
    """Read-only history of this employer's completed job postings —
    jobs whose interview date has passed and were archived + permanently
    removed from the live listings by the archive_completed_jobs
    management command."""
    employer = Employer.objects.filter(user=request.user).first()
    if employer is None:
        messages.error(request, "That page is only available to employer accounts.")
        return redirect("job_boardApp:home")

    audits = JobAudit.objects.filter(employer_username=request.user.username)

    context = {
        "page_title": "Audit History",
        "audits": audits,
    }
    return render(request, "job_boardApp/audit_history.html", context)


@login_required
def post_job(request):
    employer = Employer.objects.filter(user=request.user).first()
    if employer is None:
        messages.error(request, "Only employer accounts can post jobs.")
        return redirect("job_boardApp:home")

    if request.method == "POST":
        Job.objects.create(
            employer=employer,
            title=request.POST.get("title"),
            description=request.POST.get("description", ""),
            required_skills=request.POST.get("required_skills", ""),
            location=request.POST.get("location", ""),
            min_experience=int(request.POST.get("min_experience") or 0),
            salary=request.POST.get("salary", ""),
        )
        
        messages.success(request, "Job posted! We're matching it against candidates now.")
        return redirect("job_boardApp:employer_dashboard")

    return render(request, "job_boardApp/post_job.html", {"page_title": "Post a Job", "employer": employer})


@login_required
def close_job(request, job_id):
   
    employer = get_object_or_404(Employer, user=request.user)
    job = get_object_or_404(Job, id=job_id, employer=employer)

    if request.method != "POST":
        messages.error(request, "Closing a vacancy requires confirmation.")
        return redirect("job_boardApp:employer_dashboard")

    job_title = job.title
    audit = archive_and_delete_job(job, reason=JobAudit.REASON_MANUAL_CLOSE)

    messages.success(
        request,
        f"'{job_title}'+6 has been closed and archived "
        f"({audit.total_accepted} accepted, {audit.total_declined} declined, "
        f"{audit.total_no_response} awaiting response at time of closing). "
        f"It's been permanently removed from the marketplace.",
    )
    return redirect("job_boardApp:employer_dashboard")


@login_required
def candidate_detail(request, seeker_id):
    employer = get_object_or_404(Employer, user=request.user)
    seeker = get_object_or_404(JobSeeker, id=seeker_id)
    matched_jobs = JobMatch.objects.filter(job_seeker=seeker, job__employer=employer).select_related("job")
    invites = InterviewInvite.objects.filter(employer=employer, job_seeker=seeker).select_related("match__job")
    context = {
        "page_title": seeker.full_name,
        "seeker": seeker,
        "matched_jobs": matched_jobs,
        "invites": invites,
    }
    return render(request, "job_boardApp/candidate_detail.html", context)


@login_required
def job_candidates(request, job_id):
    """Ranked list of every candidate matched to this job, with
    plain-English advice derived from their match percentages —
    who's the strongest match, whether candidates are closely tied,
    and whether it's worth interviewing more than one."""
    employer = Employer.objects.filter(user=request.user).first()
    if employer is None:
        messages.error(request, "That page is only available to employer accounts.")
        return redirect("job_boardApp:home")

    job = get_object_or_404(Job, id=job_id, employer=employer)
    matches = (
        JobMatch.objects.filter(job=job)
        .select_related("job_seeker", "job")
        .order_by("-score")
    )

    advice = generate_job_candidate_advice(matches)

    context = {
        "page_title": f"Candidates for {job.title}",
        "job": job,
        "advice": advice,
        "max_slots": MAX_INTERVIEW_SLOTS,
    }
    return render(request, "job_boardApp/job_candidates.html", context)


@login_required
def send_interview_invite(request, match_id):
    """Employer accepts a matched candidate and sends them an interview
    invite with a date, time and venue. This creates the InterviewInvite
    and immediately notifies the candidate — the notification message
    itself carries the date/time/venue so they see it right away."""
    employer = Employer.objects.filter(user=request.user).first()
    if employer is None:
        messages.error(request, "Only employer accounts can send interview invites.")
        return redirect("job_boardApp:home")

    match = get_object_or_404(JobMatch, id=match_id, job__employer=employer)

    blocking_invite = match.invites.filter(
        status__in=[InterviewInvite.STATUS_PENDING, InterviewInvite.STATUS_ACCEPTED]
    ).first()
    if blocking_invite is not None:
        messages.info(
            request,
            f"An invite for {match.job_seeker.full_name} is already "
            f"{blocking_invite.status} — no need to send another.",
        )
        return redirect("job_boardApp:candidate_detail", seeker_id=match.job_seeker.id)

    if request.method == "POST":
        interview_date = request.POST.get("interview_date")
        interview_time = request.POST.get("interview_time")
        venue = request.POST.get("venue")
        note = request.POST.get("note", "")

        if not interview_date or not interview_time or not venue:
            messages.error(request, "Date, time and venue are all required.")
            return redirect("job_boardApp:send_interview_invite", match_id=match.id)

        invite = InterviewInvite.objects.create(
            match=match,
            employer=employer,
            job_seeker=match.job_seeker,
            interview_date=interview_date,
            interview_time=interview_time,
            venue=venue,
            note=note,
        )

    
        Notification.objects.create(
            user=match.job_seeker.user,
            message=(
                f"Interview invite for {match.job.title} at {employer.company_name}: "
                f"{invite.interview_date} at {invite.interview_time}, venue: {invite.venue}. "
                f"Please accept or decline."
            ),
            link="/dashboard/",
        )

        messages.success(request, f"Interview invite sent to {match.job_seeker.full_name}.")
        return redirect("job_boardApp:candidate_detail", seeker_id=match.job_seeker.id)

    context = {
        "page_title": "Send Interview Invite",
        "match": match,
    }
    return render(request, "job_boardApp/send_interview_invite.html", context)


@login_required
def employee_dashboard(request):
    seeker = JobSeeker.objects.filter(user=request.user).first()
    if seeker is None:
        messages.error(request, "That page is only available to job seeker accounts.")
        return redirect("job_boardApp:home")
    matches = (
        JobMatch.objects.filter(job_seeker=seeker, score__gte=DASHBOARD_MIN_SCORE, dismissed_by_seeker=False)
        .exclude(invites__status__in=[InterviewInvite.STATUS_ACCEPTED, InterviewInvite.STATUS_DECLINED])
        .select_related("job", "job__employer")
    )

    invites = InterviewInvite.objects.filter(job_seeker=seeker).select_related("match__job", "employer")

    context = {
        "page_title": "My Dashboard",
        "seeker": seeker,
        "matches": matches,
        "match_count": matches.count(),
        "invites": invites,
        "pending_invite_count": invites.filter(status=InterviewInvite.STATUS_PENDING).count(),
    }
    return render(request, "job_boardApp/employee_dashboard.html", context)


@login_required
def dismiss_match(request, match_id):

    seeker = JobSeeker.objects.filter(user=request.user).first()
    if seeker is None:
        messages.error(request, "That page is only available to job seeker accounts.")
        return redirect("job_boardApp:home")

    match = get_object_or_404(JobMatch, id=match_id, job_seeker=seeker)

    if request.method != "POST":
        messages.error(request, "Dismissing a match requires confirmation.")
        return redirect("job_boardApp:employee_dashboard")

    match.dismissed_by_seeker = True
    match.save(update_fields=["dismissed_by_seeker"])
    messages.success(request, f"Removed '{match.job.title}' from your matches.")
    return redirect("job_boardApp:employee_dashboard")


@login_required
def respond_to_invite(request, invite_id, action):

    seeker = JobSeeker.objects.filter(user=request.user).first()
    if seeker is None:
        messages.error(request, "That page is only available to job seeker accounts.")
        return redirect("job_boardApp:home")

    invite = get_object_or_404(InterviewInvite, id=invite_id, job_seeker=seeker)

    if action == "accept":
        invite.status = InterviewInvite.STATUS_ACCEPTED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at"])
        Notification.objects.create(
            user=invite.employer.user,
            message=(
                f"{seeker.full_name} accepted the interview for {invite.match.job.title} "
                f"on {invite.interview_date} at {invite.interview_time}."
            ),
            link=f"/employer/candidates/{seeker.id}/",
        )
        messages.success(request, "Interview accepted. See you there!")

    elif action == "decline":
        invite.status = InterviewInvite.STATUS_DECLINED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at"])
        Notification.objects.create(
            user=invite.employer.user,
            message=f"{seeker.full_name} declined the interview for {invite.match.job.title}.",
            link=f"/employer/candidates/{seeker.id}/",
        )
        messages.info(request, "Interview declined.")

    else:
        messages.error(request, "Unknown action.")

    return redirect("job_boardApp:employee_dashboard")


@login_required
def edit_profile(request):
    seeker = JobSeeker.objects.filter(user=request.user).first()
    if seeker is None:
        messages.error(request, "That page is only available to job seeker accounts.")
        return redirect("job_boardApp:home")

    if request.method == "POST":
        new_cv = request.FILES.get("cv")
        errors = check_cv(new_cv)          # the validator from the register step

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "job_boardApp/edit_profile.html",
                          {"page_title": "Edit Profile", "seeker": seeker})

        seeker.full_name = request.POST.get("full_name", seeker.full_name)
        seeker.skills = request.POST.get("skills", seeker.skills)
        seeker.jtitle = request.POST.get("jtitle", seeker.jtitle)
        seeker.location = request.POST.get("location", seeker.location)
        experience_years_raw = request.POST.get("experience_years")
        seeker.experience_years = int(experience_years_raw) if experience_years_raw else seeker.experience_years
        seeker.bio = request.POST.get("bio", seeker.bio)
        
        seeker.esco_skills_cache = ""

        if new_cv:
            if seeker.cv:
                seeker.cv.delete(save=False)   
            seeker.cv = new_cv
            seeker.cv_text_cache = ""          

        seeker.save()
        messages.success(request, "Profile updated. Re-matching against open jobs...")
        return redirect("job_boardApp:employee_dashboard")

    return render(request, "job_boardApp/edit_profile.html", {"page_title": "Edit Profile", "seeker": seeker})

def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    return render(request, "job_boardApp/job_detail.html", {"page_title": job.title, "job": job})


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def get_notifications(request):
    notifications = (
        Notification.objects.filter(user=request.user, is_read=False)
        .order_by("-created_at")[:10]
    )
    data = [
        {
            "id": n.id,
            "message": n.message,
            "link": n.link,
            "created_at": n.created_at.strftime("%b %d, %H:%M"),
        }
        for n in notifications
    ]
    return JsonResponse({"notifications": data, "count": len(data)})


@login_required
@require_POST
def mark_notification_read(request, notification_id):
 
    updated = Notification.objects.filter(
        id=notification_id, user=request.user
    ).update(is_read=True)

    if updated == 0:
        return JsonResponse(
            {"status": "error", "message": "This notification no longer exists."},
            status=404,
        )
    return JsonResponse({"status": "success"})


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "success"})

def _role_and_actor_for_invite(request, invite):
    """Return (role, ok) for whoever is logged in relative to this
    invite — 'employer' or 'seeker' — or (None, False) if the current
    user has nothing to do with this invite at all."""
    employer = Employer.objects.filter(user=request.user).first()
    if employer is not None and invite.employer_id == employer.id:
        return Feedback.ROLE_EMPLOYER, True

    seeker = JobSeeker.objects.filter(user=request.user).first()
    if seeker is not None and invite.job_seeker_id == seeker.id:
        return Feedback.ROLE_SEEKER, True

    return None, False


@login_required
def submit_feedback(request, invite_id):
    invite = get_object_or_404(InterviewInvite, id=invite_id)
    role, ok = _role_and_actor_for_invite(request, invite)
    if not ok:
        messages.error(request, "You don't have access to leave feedback on this interview.")
        return redirect("job_boardApp:home")

    if invite.status == InterviewInvite.STATUS_PENDING:
        messages.info(request, "Feedback can be left once the invite has been accepted or declined.")
        return redirect("job_boardApp:home")

    existing = Feedback.objects.filter(invite=invite, submitted_by_user=request.user).first()

    if request.method == "POST":
        rating = request.POST.get("rating")
        comments = request.POST.get("comments", "")
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            rating = 0

        if rating < 1 or rating > 5:
            messages.error(request, "Please choose a rating from 1 to 5.")
        else:
            if existing:
                existing.rating = rating
                existing.comments = comments
                existing.save(update_fields=["rating", "comments"])
                messages.success(request, "Feedback updated. Thanks!")
            else:
                Feedback.objects.create(
                    invite=invite,
                    submitted_by_role=role,
                    submitted_by_user=request.user,
                    rating=rating,
                    comments=comments,
                )
                messages.success(request, "Thanks for your feedback!")

            return redirect("job_boardApp:employer_dashboard" if role == Feedback.ROLE_EMPLOYER else "job_boardApp:employee_dashboard")

    context = {
        "page_title": "Leave Feedback",
        "invite": invite,
        "existing": existing,
    }
    return render(request, "job_boardApp/submit_feedback.html", context)


@login_required
def employer_analytics(request):
    """Snapshot of an employer's hiring funnel — combining LIVE data
    (from currently open jobs) with HISTORICAL data preserved in
    JobAudit for jobs that have since been closed/archived. Without
    the historical half, every number here would reset toward zero
    each time a job gets archived, since archiving cascade-deletes the
    live JobMatch/InterviewInvite/Feedback rows."""
    employer = Employer.objects.filter(user=request.user).first()
    if employer is None:
        messages.error(request, "That page is only available to employer accounts.")
        return redirect("job_boardApp:home")

    jobs = Job.objects.filter(employer=employer)
    live_matches = JobMatch.objects.filter(job__employer=employer)
    live_invites = InterviewInvite.objects.filter(employer=employer)
    live_feedback = Feedback.objects.filter(invite__employer=employer)

    live_match_count = live_matches.count()
    live_match_score_sum = (live_matches.aggregate(avg=Avg("score"))["avg"] or 0) * live_match_count
    live_invite_count = live_invites.count()
    live_accepted = live_invites.filter(status=InterviewInvite.STATUS_ACCEPTED).count()
    live_declined = live_invites.filter(status=InterviewInvite.STATUS_DECLINED).count()
    live_pending = live_invites.filter(status=InterviewInvite.STATUS_PENDING).count()
    live_feedback_count = live_feedback.count()
    live_feedback_sum = (live_feedback.aggregate(avg=Avg("rating"))["avg"] or 0) * live_feedback_count

    audits = JobAudit.objects.filter(employer_username=request.user.username)
    hist_match_count = sum(a.total_matches for a in audits)
    hist_match_score_sum = sum(a.avg_match_score * a.total_matches / 100 for a in audits)  # avg_match_score is a %, convert back to 0-1 scale weighted by count
    hist_invite_count = sum(a.total_invites_sent for a in audits)
    hist_accepted = sum(a.total_accepted for a in audits)
    hist_declined = sum(a.total_declined for a in audits)
    hist_pending = sum(a.total_no_response for a in audits)
    hist_feedback_count = sum(a.feedback_count for a in audits)
    hist_feedback_sum = sum(a.avg_feedback_rating * a.feedback_count for a in audits)

    total_matches = live_match_count + hist_match_count
    total_invites = live_invite_count + hist_invite_count
    total_accepted = live_accepted + hist_accepted
    total_declined = live_declined + hist_declined
    total_pending = live_pending + hist_pending
    total_feedback_count = live_feedback_count + hist_feedback_count

    avg_match_score = round(
        ((live_match_score_sum + hist_match_score_sum) / total_matches) * 100
    ) if total_matches else 0

    avg_satisfaction = round(
        (live_feedback_sum + hist_feedback_sum) / total_feedback_count, 1
    ) if total_feedback_count else 0

    context = {
        "page_title": "Analytics",
        "employer": employer,
        "total_jobs": jobs.count() + audits.count(),
        "active_jobs": jobs.filter(is_active=True).count(),
        "total_matches": total_matches,
        "avg_match_score": avg_match_score,
        "total_invites": total_invites,
        "invites_accepted": total_accepted,
        "invites_declined": total_declined,
        "invites_pending": total_pending,
        "acceptance_rate": round((total_accepted / total_invites) * 100) if total_invites else 0,
        "avg_satisfaction": avg_satisfaction,
        "feedback_count": total_feedback_count,
        "archived_jobs": audits.count(),
    }
    return render(request, "job_boardApp/employer_analytics.html", context)


@login_required
def seeker_analytics(request):
    """Snapshot for a job seeker — combining LIVE data (matches/invites
    still on active jobs) with HISTORICAL data preserved in SeekerAudit
    for jobs that have since been closed/archived. Without the
    historical half, a seeker's stats would drop every time an employer
    archives a job they'd matched or interviewed for."""
    seeker = JobSeeker.objects.filter(user=request.user).first()
    if seeker is None:
        messages.error(request, "That page is only available to job seeker accounts.")
        return redirect("job_boardApp:home")
    live_matches = JobMatch.objects.filter(job_seeker=seeker)
    live_invites = InterviewInvite.objects.filter(job_seeker=seeker)
    live_feedback = Feedback.objects.filter(invite__job_seeker=seeker)
    live_match_count = live_matches.count()
    live_match_score_sum = (live_matches.aggregate(avg=Avg("score"))["avg"] or 0) * live_match_count
    live_invite_count = live_invites.count()
    live_accepted = live_invites.filter(status=InterviewInvite.STATUS_ACCEPTED).count()
    live_declined = live_invites.filter(status=InterviewInvite.STATUS_DECLINED).count()
    live_pending = live_invites.filter(status=InterviewInvite.STATUS_PENDING).count()
    live_feedback_count = live_feedback.count()
    live_feedback_sum = (live_feedback.aggregate(avg=Avg("rating"))["avg"] or 0) * live_feedback_count

    historical = SeekerAudit.objects.filter(seeker_username=request.user.username)
    hist_match_count = historical.count()
    hist_match_score_sum = sum(h.match_score or 0 for h in historical)
    hist_invited = historical.exclude(invite_status="")
    hist_invite_count = hist_invited.count()
    hist_accepted = historical.filter(invite_status=InterviewInvite.STATUS_ACCEPTED).count()
    hist_declined = historical.filter(invite_status=InterviewInvite.STATUS_DECLINED).count()
    hist_pending = historical.filter(invite_status=InterviewInvite.STATUS_PENDING).count()
    hist_rated = historical.exclude(feedback_rating_given__isnull=True)
    hist_feedback_count = hist_rated.count()
    hist_feedback_sum = sum(h.feedback_rating_given for h in hist_rated)

    total_matches = live_match_count + hist_match_count
    total_invites = live_invite_count + hist_invite_count
    total_accepted = live_accepted + hist_accepted
    total_declined = live_declined + hist_declined
    total_pending = live_pending + hist_pending
    total_feedback_count = live_feedback_count + hist_feedback_count

    avg_match_score = round(
        ((live_match_score_sum + hist_match_score_sum) / total_matches) * 100
    ) if total_matches else 0

    avg_satisfaction_given = round(
        (live_feedback_sum + hist_feedback_sum) / total_feedback_count, 1
    ) if total_feedback_count else 0

    context = {
        "page_title": "My Analytics",
        "seeker": seeker,
        "total_matches": total_matches,
        "avg_match_score": avg_match_score,
        "total_invites": total_invites,
        "invites_accepted": total_accepted,
        "invites_declined": total_declined,
        "invites_pending": total_pending,
        "avg_satisfaction_given": avg_satisfaction_given,
        "feedback_count": total_feedback_count,
    }
    return render(request, "job_boardApp/seeker_analytics.html", context)
