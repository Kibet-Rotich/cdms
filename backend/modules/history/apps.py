from django.apps import AppConfig


class HistoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.history"
    label = "history"

    def ready(self):
        from . import handlers

        handlers.register()
