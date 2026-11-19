from django.apps import AppConfig


class job_boardAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "job_boardApp"

    def ready(self):
        import job_boardApp.signals  # noqa: F401
