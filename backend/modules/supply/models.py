from django.db import models

from core.models import BaseModel, CountyScoped


class StockReceipt(BaseModel, CountyScoped):
    """Stock of a monitored medicine received by a facility. Mocked now; PPB track-and-trace later."""

    facility_id = models.UUIDField(db_index=True)
    drug_id = models.UUIDField(db_index=True)
    batch_number = models.CharField(max_length=40, blank=True, default="")
    gtin = models.CharField(max_length=20, blank=True, default="", help_text="Global Trade Item Number (future T&T)")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    supplier_name = models.CharField(max_length=150, blank=True, default="")
    received_at = models.DateTimeField(db_index=True)
    recorded_by = models.UUIDField(null=True, blank=True)
    source = models.CharField(max_length=20, default="MANUAL")  # MANUAL | MOCK_TT | TRACK_AND_TRACE

    class Meta:
        ordering = ["-received_at"]
