import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    """Append-only audit log. Each row stores the hash of the previous row (tamper evidence)."""

    seq = models.BigAutoField(primary_key=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_name = models.CharField(max_length=150, blank=True, default="")
    actor_role = models.CharField(max_length=20, blank=True, default="")
    facility_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=60, db_index=True)  # e.g. READ, SEARCH, EVENT:DispenseRecorded
    resource_type = models.CharField(max_length=60)
    resource_id = models.CharField(max_length=64, blank=True, default="")
    patient_id = models.UUIDField(null=True, blank=True, db_index=True)
    purpose = models.CharField(max_length=30, blank=True, default="")
    ip_address = models.CharField(max_length=45, blank=True, default="")
    details = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["-seq"]

    def compute_hash(self):
        body = json.dumps(
            {
                "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
                "actor_id": str(self.actor_id) if self.actor_id else None,
                "action": self.action,
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
                "patient_id": str(self.patient_id) if self.patient_id else None,
                "purpose": self.purpose,
                "details": self.details,
                "prev_hash": self.prev_hash,
            },
            sort_keys=True,
            cls=DjangoJSONEncoder,
        )
        return hashlib.sha256(body.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.seq is not None:
            raise RuntimeError("Audit events are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit events are append-only and cannot be deleted.")
