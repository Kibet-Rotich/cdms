import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


def pilot_county():
    return settings.PILOT_COUNTY_CODE


class BaseModel(models.Model):
    """Common fields for every business record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CountyScoped(models.Model):
    """Every patient- or facility-related row is tagged by county (multi-county readiness)."""

    county_code = models.CharField(max_length=3, default=pilot_county, db_index=True)

    class Meta:
        abstract = True


class OutboxEvent(models.Model):
    """Domain events written in the same transaction as the change (transactional outbox).

    Today an in-process dispatcher delivers them; later a message broker can read this table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.name} @ {self.created_at:%Y-%m-%d %H:%M}"
