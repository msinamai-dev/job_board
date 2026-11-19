

# How many people you actually want to interview. Change this if your
# interview capacity changes — everything below adapts automatically.
MAX_INTERVIEW_SLOTS = 3


def categorize_score(score):
    """Return (label, bootstrap_color) for a given match score (0.0-1.0)."""
    if score >= 0.85:
        return "Excellent Match", "success"
    if score >= 0.70:
        return "Strong Match", "primary"
    if score >= 0.50:
        return "Moderate Match", "warning"
    return "Weak Match", "secondary"


def _same_location(match):
    seeker_location = (match.job_seeker.location or "").strip().lower()
    job_location = (match.job.location or "").strip().lower()
    return bool(seeker_location) and seeker_location == job_location


def _has_cv(match):
    return bool(getattr(match.job_seeker, "cv", None))


def _tie_break_sort_key(match):
   
    return (
        -round(match.score, 4),
        -(match.job_seeker.experience_years or 0),
        0 if _same_location(match) else 1,
        0 if _has_cv(match) else 1,
        match.matched_at,
    )


def _tie_break_signature(match):
  
    return (
        round(match.score, 4),
        match.job_seeker.experience_years or 0,
        _same_location(match),
        _has_cv(match),
    )


def _rank_matches(matches):
  
    return sorted(matches, key=_tie_break_sort_key)


def _describe_tiebreak(shortlisted, waitlisted):
    
    if not shortlisted or not waitlisted:
        return None

    last_in = shortlisted[-1]
    first_out = waitlisted[0]

    if _tie_break_signature(last_in) == _tie_break_signature(first_out):
        return (
            f"⚠️ {last_in.job_seeker.full_name} and {first_out.job_seeker.full_name} "
            f"are tied on every signal we check (score, experience, location, CV on file) — "
            f"{last_in.job_seeker.full_name} only edged in for the last interview slot because "
            f"they matched first. You may want to interview both if you have any flexibility."
        )

    if round(last_in.score, 2) != round(first_out.score, 2):
        return None  # score alone already separated them — nothing extra to explain

    if (last_in.job_seeker.experience_years or 0) != (first_out.job_seeker.experience_years or 0):
        return (
            f"{last_in.job_seeker.full_name} and {first_out.job_seeker.full_name} matched at the "
            f"same score — {last_in.job_seeker.full_name} got the last interview slot for having "
            f"more relevant experience ({last_in.job_seeker.experience_years} vs "
            f"{first_out.job_seeker.experience_years} years)."
        )

    if _same_location(last_in) != _same_location(first_out):
        return (
            f"{last_in.job_seeker.full_name} and {first_out.job_seeker.full_name} matched at the "
            f"same score and experience — {last_in.job_seeker.full_name} got the last interview "
            f"slot for being based in the same location as the job."
        )

    if _has_cv(last_in) != _has_cv(first_out):
        return (
            f"{last_in.job_seeker.full_name} and {first_out.job_seeker.full_name} were tied on "
            f"score, experience and location — {last_in.job_seeker.full_name} got the last "
            f"interview slot for having a CV on file to review."
        )

    return None


def generate_job_candidate_advice(matches, max_slots=MAX_INTERVIEW_SLOTS):
    
    matches = list(matches)

    if not matches:
        return {
            "summary": "No candidates have matched this job yet. "
                       "Check back once more job seekers sign up, or "
                       "widen the required skills if this persists.",
            "tiebreak_note": None,
            "candidates": [],
        }

    ranked = _rank_matches(matches)
    shortlisted = ranked[:max_slots]
    waitlisted = ranked[max_slots:]

    candidates = []
    for m in ranked:
        label, color = categorize_score(m.score)
        candidates.append({
            "match": m,
            "label": label,
            "color": color,
            "percentage": round(m.score * 100),
            "recommended": m in shortlisted,
        })

    tiebreak_note = _describe_tiebreak(shortlisted, waitlisted)

    if len(matches) <= max_slots:
        names = ", ".join(m.job_seeker.full_name for m in shortlisted)
        summary = (
            f"{len(matches)} candidate(s) matched this job — within your "
            f"{max_slots}-slot interview capacity, so you can interview "
            f"all of them: {names}."
        )
    else:
        names = ", ".join(m.job_seeker.full_name for m in shortlisted)
        top_score = shortlisted[0].score
        summary = (
            f"{len(matches)} candidates matched, but you only have "
            f"{max_slots} interview slots. Based on match score plus experience, "
            f"location and Skill as tiebreakers, the recommended shortlist is: "
            f"{names} (top match: {round(top_score * 100)}%)."
        )

    return {
        "summary": summary,
        "tiebreak_note": tiebreak_note,
        "candidates": candidates,
    }
