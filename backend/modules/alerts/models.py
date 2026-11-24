from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from core.models import BaseModel, CountyScoped


class RuleConfig(models.Model):
    """Admin-editable thresholds per rule (FR-H2). Missing keys fall back to the rule's defaults."""

    code = models.CharField(max_length=40, primary_key=True)
    enabled = models.BooleanField(default=True)
    params = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return self.code


class Evaluation(BaseModel):
    """Result of a `preview` call. The commit re-evaluates and references this for traceability."""

    action = models.CharField(max_length=10)  # PRESCRIBE | DISPENSE
    patient_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField(null=True, blank=True)
    facility_id = models.UUIDField(null=True, blank=True)
    proposed = models.JSONField(encoder=DjangoJSONEncoder)
    findings = models.JSONField(encoder=DjangoJSONEncoder, default=list)


class Alert(BaseModel, CountyScoped):
    """An alert raised on a committed prescription or dispense, with the user's acknowledgement."""

    class AckReason(models.TextChoices):
        CLINICALLY_JUSTIFIED = "CLINICALLY_JUSTIFIED", "Clinically justified"
        VERIFIED_WITH_PRESCRIBER = "VERIFIED_WITH_PRESCRIBER", "Verified with prescriber"
        PATIENT_LOST_MEDICATION = "PATIENT_LOST_MEDICATION", "Patient lost medication"
        DOSE_CHANGE = "DOSE_CHANGE", "Dose change / new regimen"
        PALLIATIVE_CARE = "PALLIATIVE_CARE", "Palliative / cancer care"
        OTHER = "OTHER", "Other (note required)"

    evaluation = models.ForeignKey(Evaluation, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=10)
    subject_type = models.CharField(max_length=20)  # Prescription | Dispense
    subject_id = models.UUIDField()
    patient_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField(null=True, blank=True, db_index=True)
    prescriber_key = models.CharField(max_length=40, blank=True, default="", db_index=True)
    rule_code = models.CharField(max_length=40, db_index=True)
    severity = models.CharField(max_length=10, db_index=True)
    title = models.CharField(max_length=100)
    message = models.TextField()
    details = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    acknowledged_by = models.UUIDField(null=True, blank=True)
    acknowledged_by_name = models.CharField(max_length=150, blank=True, default="")
    ack_reason = models.CharField(max_length=30, choices=AckReason.choices)
    ack_note = models.TextField(blank=True, default="")
    referral_made = models.BooleanField(default=False)
    referral_note = models.TextField(blank=True, default="")
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
