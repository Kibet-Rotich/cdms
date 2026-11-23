from django.db import models

from core.models import BaseModel, CountyScoped


class Dispense(BaseModel, CountyScoped):
    """A supply of a monitored medicine handed to a patient, against an e-prescription or a paper one."""

    class Status(models.TextChoices):
        RECORDED = "RECORDED", "Recorded"
        VOIDED = "VOIDED", "Voided"

    patient_id = models.UUIDField(db_index=True)
    prescription_id = models.UUIDField(null=True, blank=True, db_index=True)  # null for paper prescriptions
    drug_id = models.UUIDField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    days_supply = models.PositiveIntegerField()
    batch_number = models.CharField(max_length=40, blank=True, default="")
    facility_id = models.UUIDField(db_index=True)
    pharmacist_id = models.UUIDField()
    pharmacist_name = models.CharField(max_length=150)
    # Who prescribed it (copied from the e-prescription, or typed from the paper prescription)
    prescriber_name = models.CharField(max_length=150, blank=True, default="")
    prescriber_licence = models.CharField(max_length=30, blank=True, default="")
    # Paper prescription fields
    is_paper = models.BooleanField(default=False)
    paper_rx_date = models.DateField(null=True, blank=True)
    paper_rx_number = models.CharField(max_length=40, blank=True, default="")
    paper_prescriber_facility = models.CharField(max_length=150, blank=True, default="")
    paper_licence_verified = models.BooleanField(default=False)

    dispensed_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECORDED)
    void_reason = models.CharField(max_length=255, blank=True, default="")
    voided_by = models.UUIDField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    evaluation_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-dispensed_at"]
