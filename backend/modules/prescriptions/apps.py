from django.apps import AppConfig


class PrescriptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.prescriptions"
    label = "prescriptions"

    def ready(self):
        from core.events import subscribe

        from . import services

        subscribe("DispenseRecorded", services.on_dispense_recorded)
        subscribe("DispenseVoided", services.on_dispense_voided)
