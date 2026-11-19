from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Job, JobSeeker
from .matching import match_job_to_seekers, match_seeker_to_jobs


def _is_cache_only_save(kwargs):
    """True if this save only touched esco_skills_cache — which happens
    when matching.py caches an ESCO lookup via job.save(update_fields=[...])
    or seeker.save(update_fields=[...]). Without this check, that save
    re-triggers this very signal, which re-runs matching, which saves the
    cache again — a redundant (though self-terminating) double pass."""
    update_fields = kwargs.get("update_fields")
    return bool(update_fields) and set(update_fields) == {"esco_skills_cache"}


@receiver(post_save, sender=Job)
def job_saved(sender, instance, created, **kwargs):
    if _is_cache_only_save(kwargs):
        return
    if instance.is_active:
        match_job_to_seekers(instance)


@receiver(post_save, sender=JobSeeker)
def seeker_saved(sender, instance, created, **kwargs):
    if _is_cache_only_save(kwargs):
        return
    match_seeker_to_jobs(instance)