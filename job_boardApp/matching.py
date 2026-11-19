import difflib

from .models import Job, JobSeeker, JobMatch, Notification
from . import esco_client

try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:  # falls back to difflib if rapidfuzz isn't installed
    _HAS_RAPIDFUZZ = False

MATCH_THRESHOLD = 0.65  


_EMPTY_ESCO_SENTINEL = "\x00EMPTY\x00"

SKILL_CATEGORIES = {
    "IT": [
        "it", "Information technology", "computer", "software", "developer",
        "programmer", "network", "systems admin", "sysadmin", "technician",
        "helpdesk", "help desk", "support", "hardware", "database", "sql",
        "python", "java", "web developer", "cybersecurity", "cloud",
    ],
    "accounting": [
        "accounting", "accountant", "bookkeeper", "bookkeeping", "finance",
        "financial", "audit", "auditor", "tax", "payroll", "ledger",
        "reconciliation", "quickbooks", "pastel",
    ],
    "sales": [
        "sales", "salesperson", "business development", "account manager",
        "retail", "cashier", "sales rep", "marketing", "customer service",
    ],
    "admin": [
        "admin", "administrator", "administration", "receptionist",
        "office assistant", "clerk", "secretary", "data entry",
    ],
    "hr": [
        "HR", "Human Resources", "recruiter", "recruitment", "talent",
    ],
    "logistics": [
        "logistics", "warehouse", "driver", "supply chain", "procurement",
        "inventory", "dispatch",
    ],
}

# Common skill abbreviations/aliases so "JS" and "JavaScript", or "Excel"
# and "Microsoft Excel", are recognised as the same skill before exact/
# fuzzy comparison. Extend this as you notice more mismatches in practice.
SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "excel": "microsoft excel",
    "ms excel": "microsoft excel",
    "word": "microsoft word",
    "ms word": "microsoft word",
    "powerpoint": "microsoft powerpoint",
    "ppt": "microsoft powerpoint",
    "py": "python",
    "sql server": "sql",
    "mssql": "sql",
    "postgres": "postgresql",
    "hr": "human resources",
    "cx": "customer service",
    "cs": "customer service",
    "biz dev": "business development",
    "bd": "business development",
    "qb": "quickbooks",
}


def _normalize_skill(skill):
    skill = skill.strip().lower()
    return SKILL_ALIASES.get(skill, skill)


def _seeker_profile_text(seeker):
    return " ".join([
        getattr(seeker, "jtitle", "") or "",
        getattr(seeker, "skills", "") or "",
        getattr(seeker, "bio", "") or "",
        getattr(seeker, "cv_text_cache", "") or "",
    ])


def _get_or_fetch_job_esco_labels(job):
    if job.esco_skills_cache:
        if job.esco_skills_cache == _EMPTY_ESCO_SENTINEL:
            return set()
        return set(job.esco_skills_cache.split("|"))

    labels = esco_client.get_related_labels(job.title)
    job.esco_skills_cache = "|".join(sorted(labels)) if labels else _EMPTY_ESCO_SENTINEL
    job.save(update_fields=["esco_skills_cache"])
    return labels


def _get_or_fetch_seeker_esco_labels(seeker):
    if seeker.esco_skills_cache:
        if seeker.esco_skills_cache == _EMPTY_ESCO_SENTINEL:
            return set()
        return set(seeker.esco_skills_cache.split("|"))

    lookup_text = (getattr(seeker, "jtitle", "") or "").strip()

    if not lookup_text:
        first_skill = next(
            (s.strip() for s in (seeker.skills or "").split(",") if s.strip()), ""
        )
        lookup_text = first_skill

    if not lookup_text:
        cv_text = (getattr(seeker, "cv_text_cache", "") or "").strip()
        if cv_text:
            lookup_text = cv_text.split("\n")[0][:100]

    if not lookup_text:
        return set()

    labels = esco_client.get_related_labels(lookup_text)
    seeker.esco_skills_cache = "|".join(sorted(labels)) if labels else _EMPTY_ESCO_SENTINEL
    seeker.save(update_fields=["esco_skills_cache"])
    return labels


def _esco_category_score(job, seeker):
    job_labels = _get_or_fetch_job_esco_labels(job)
    seeker_labels = _get_or_fetch_seeker_esco_labels(seeker)
    if not job_labels or not seeker_labels:
        return 0.0
    return 1.0 if job_labels & seeker_labels else 0.0


def _text_categories(text):
    text = (text or "").lower()
    matched = set()
    for category, keywords in SKILL_CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            matched.add(category)
    return matched


def _category_score(job, seeker):
    """1.0 if job and seeker share a recognised category (e.g. both 'it'),
    0 otherwise. Lets 'IT Technician' match 'IT Assistant' even with no
    exact skill overlap. Seeker side now includes jtitle + CV text, not
    just skills/bio, so a CV mentioning IT work counts too."""
    job_text = f"{job.title} {job.required_skills}"
    seeker_text = _seeker_profile_text(seeker)
    job_categories = _text_categories(job_text)
    seeker_categories = _text_categories(seeker_text)
    return 1.0 if job_categories & seeker_categories else 0.0


def _pair_similarity(a, b):
    """Word-order-insensitive similarity between two short phrases.
    Uses rapidfuzz's token_set_ratio when available (handles "IT Support
    Technician" vs "Support Technician, IT" as near-identical); falls
    back to difflib.SequenceMatcher if rapidfuzz isn't installed."""
    if not a or not b:
        return 0.0
    if _HAS_RAPIDFUZZ:
        return fuzz.token_set_ratio(a, b) / 100
    return difflib.SequenceMatcher(None, a, b).ratio()


def _fuzzy_skill_score(job_skills, seeker_skills):
    """Give partial credit for near-identical skill phrases (e.g.
    'IT Technician' vs 'IT Technition' typo, or 'Sales Rep' vs 'Sales
    Representative') that exact-match would miss entirely."""
    if not job_skills or not seeker_skills:
        return 0
    best_scores = []
    for js in job_skills:
        best = max((_pair_similarity(js, ss) for ss in seeker_skills), default=0)
        best_scores.append(best)
    return sum(best_scores) / len(best_scores)


def _title_score(job, seeker):
    """Direct job-title <-> seeker-title comparison. Uses word-order-
    insensitive similarity so phrasing differences like:

        Job title:    "IT Support Technician"
        Seeker jtitle: "Technician, IT Support"

    still score highly, which plain SequenceMatcher would miss."""
    job_title = (getattr(job, "title", "") or "").strip().lower()
    seeker_title = (getattr(seeker, "jtitle", "") or "").strip().lower()
    return _pair_similarity(job_title, seeker_title)


def _cv_text_skill_score(job_skills, seeker):
    """Extra credit if the job's required skills literally appear
    somewhere in the seeker's CV text, even if they didn't also list
    that skill in their structured `skills` field. This is intentionally
    lighter-weight than the exact/fuzzy skill scores — a mention in a CV
    is a weaker signal than a declared skill."""
    cv_text = (getattr(seeker, "cv_text_cache", "") or "").lower()
    if not cv_text or not job_skills:
        return 0.0
    hits = sum(1 for skill in job_skills if skill in cv_text)
    return hits / len(job_skills)


def _experience_score(job, seeker):
    """Graded instead of all-or-nothing: someone 1 year short of a
    5-year requirement scores much better than someone with zero
    experience, rather than both getting a flat 0.5."""
    min_exp = getattr(job, "min_experience", 0) or 0
    seeker_exp = getattr(seeker, "experience_years", 0) or 0
    if min_exp <= 0:
        return 1.0
    if seeker_exp >= min_exp:
        return 1.0
    return round(max(seeker_exp / min_exp, 0.0), 2)


def _location_score(job, seeker):
    """Tiered instead of all-or-nothing. Falls back to the old flat
    0.3 "different location" score if the optional `province`/
    `open_to_remote` fields aren't present on your models yet — add
    them to your Job/JobSeeker models to get the finer-grained tiers."""
    job_loc = (getattr(job, "location", "") or "").strip().lower()
    seeker_loc = (getattr(seeker, "location", "") or "").strip().lower()

    if job_loc == "remote" or getattr(seeker, "open_to_remote", False):
        return 1.0
    if job_loc and job_loc == seeker_loc:
        return 1.0

    job_province = (getattr(job, "province", "") or "").strip().lower()
    seeker_province = (getattr(seeker, "province", "") or "").strip().lower()
    if job_province and job_province == seeker_province:
        return 0.6

    return 0.3


def calculate_match_score(job, seeker):
    job_skills = {_normalize_skill(s) for s in (job.required_skills or "").split(",") if s.strip()}
    seeker_skills = {_normalize_skill(s) for s in (seeker.skills or "").split(",") if s.strip()}

    if not job_skills:
        return 0
    overlap = job_skills & seeker_skills
    exact_score = len(overlap) / len(job_skills)
    fuzzy_score = _fuzzy_skill_score(job_skills, seeker_skills)
    title_score = _title_score(job, seeker)
    esco_score = _esco_category_score(job, seeker)
    local_category_score = _category_score(job, seeker)
    category_score = max(esco_score, local_category_score)
    cv_score = _cv_text_skill_score(job_skills, seeker)
    skill_score = max(
        exact_score,
        fuzzy_score * 0.8,
        category_score * 0.7,
        cv_score * 0.6,
    )

    location_score = _location_score(job, seeker)
    experience_score = _experience_score(job, seeker)

    total = (
        (skill_score * 0.45)
        + (title_score * 0.15)
        + (location_score * 0.2)
        + (experience_score * 0.2)
    )
    return round(min(total, 1.0), 2)


def notify_match(job, seeker):
    Notification.objects.create(
        user=seeker.user,
        message=f"New job match: {job.title} at {job.employer.company_name}",
        link=f"/jobs/{job.id}/",
    )
    Notification.objects.create(
        user=job.employer.user,
        message=f"New candidate match for {job.title}: {seeker.full_name}",
        link=f"/employer/candidates/{seeker.id}/",
    )


def match_job_to_seekers(job):
    for seeker in JobSeeker.objects.all():
        score = calculate_match_score(job, seeker)
        if score >= MATCH_THRESHOLD:
            match, created = JobMatch.objects.get_or_create(
                job=job, job_seeker=seeker, defaults={"score": score}
            )
            if created:
                notify_match(job, seeker)
            elif match.score != score:
                match.score = score
                match.save(update_fields=["score"])
        else:
            JobMatch.objects.filter(job=job, job_seeker=seeker, dismissed_by_seeker=False).delete()


def match_seeker_to_jobs(seeker):
    for job in Job.objects.filter(is_active=True):
        score = calculate_match_score(job, seeker)
        if score >= MATCH_THRESHOLD:
            match, created = JobMatch.objects.get_or_create(
                job=job, job_seeker=seeker, defaults={"score": score}
            )
            if created:
                notify_match(job, seeker)
            elif match.score != score:
                match.score = score
                match.save(update_fields=["score"])
        else:
            JobMatch.objects.filter(job=job, job_seeker=seeker, dismissed_by_seeker=False).delete()