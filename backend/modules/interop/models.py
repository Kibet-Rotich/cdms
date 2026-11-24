from django.db import models


class MockRegistryRecord(models.Model):
    """Stand-in for national registries during the MVP (DHA Client Registry, KMPDC/PPB registers).

    Lives behind the same adapter interface the live APIs will use, so switching INTEROP_MODE
    to "live" later does not change any other module.
    """

    class Kind(models.TextChoices):
        CLIENT = "CLIENT", "DHA Client Registry person"
        PRACTITIONER = "PRACTITIONER", "Practitioner register entry"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    key = models.CharField(max_length=80, help_text="CLIENT: '<ID_TYPE>:<number>'; PRACTITIONER: licence number")
    data = models.JSONField()

    class Meta:
        unique_together = [("kind", "key")]

    def __str__(self):
        return f"{self.kind} {self.key}"
