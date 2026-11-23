from django.db import models

from core.models import BaseModel, CountyScoped


class MedicationEvent(BaseModel, CountyScoped):
    """Read model: one row per prescription issued or dispense recorded, denormalised for fast timelines.

    Built only from domain events (PrescriptionCreated, DispenseRecorded, ...). It can be rebuilt from the
    outbox at any time, which is why it never calls the Prescription or Dispensing modules directly.
    """

    class Kind(models.TextChoices):
        PRESCRIBED = "PRESCRIBED", "Prescribed"
        DISPENSED = "DISPENSED", "Dispensed"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        VOIDED = "VOIDED", "Voided"
        CANCELLED = "CANCELLED", "Cancelled"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    source_id = models.UUIDField(help_text="Prescription or dispense ID")
    prescription_id = models.UUIDField(null=True, blank=True)
    patient_id = models.UUIDField(db_index=True)
    drug_id = models.UUIDField()
    drug_name = models.CharField(max_length=150)
    class_code = models.CharField(max_length=30, db_index=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    days_supply = models.PositiveIntegerField()
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()
    daily_mme = models.DecimalField(max_digits=10, decimal_places=1, default=0)
    prescriber_key = models.CharField(max_length=40, blank=True, default="", help_text="Prescriber licence number")
    prescriber_name = models.CharField(max_length=150, blank=True, default="")
    facility_id = models.UUIDField(null=True, blank=True)
    facility_name = models.CharField(max_length=150, blank=True, default="")
    sub_county = models.CharField(max_length=60, blank=True, default="")
    is_paper = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    occurred_at = models.DateTimeField()

    class Meta:
        ordering = ["-occurred_at"]
        unique_together = [("kind", "source_id")]
        indexes = [models.Index(fields=["patient_id", "start_date"])]
