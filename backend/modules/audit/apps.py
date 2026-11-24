from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.audit"
    label = "audit"

    def ready(self):
        from . import handlers

        handlers.register()
