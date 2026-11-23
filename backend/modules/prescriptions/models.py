from django.db import models

from core.models import BaseModel, CountyScoped


class Prescription(BaseModel, CountyScoped):
    """Electronic prescription for one monitored medicine (one item per prescription in the MVP)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Fully dispensed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    code = models.CharField(max_length=12, unique=True, help_text="Short code / QR content given to the patient")
    patient_id = models.UUIDField(db_index=True)
    prescriber_id = models.UUIDField(db_index=True)
    prescriber_name = models.CharField(max_length=150)
    prescriber_licence = models.CharField(max_length=30)
    facility_id = models.UUIDField()
    drug_id = models.UUIDField()
    dosage_instructions = models.CharField(max_length=255, help_text="e.g. 1 capsule three times daily")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Units per fill")
    days_supply = models.PositiveIntegerField()
    refills_allowed = models.PositiveSmallIntegerField(default=0)
    quantity_dispensed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    diagnosis_note = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    cancelled_reason = models.CharField(max_length=255, blank=True, default="")
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-issued_at"]

    @property
    def total_authorised(self):
        return self.quantity * (self.refills_allowed + 1)

    @property
    def remaining_quantity(self):
        return max(self.total_authorised - self.quantity_dispensed, 0)

    def __str__(self):
        return self.code
