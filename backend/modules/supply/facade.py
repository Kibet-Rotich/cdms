"""Public interface of the Supply module."""
from django.db.models import Sum

from .models import StockReceipt


def received_quantity_by_facility_drug(county_code, date_from, date_to):
    rows = (
        StockReceipt.objects.filter(county_code=county_code, received_at__date__gte=date_from, received_at__date__lte=date_to)
        .values("facility_id", "drug_id")
        .annotate(quantity=Sum("quantity"))
    )
    return {(str(r["facility_id"]), str(r["drug_id"])): float(r["quantity"]) for r in rows}
