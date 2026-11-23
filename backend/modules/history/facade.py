"""Public interface of the Medication History module (read model)."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from .models import MedicationEvent


def event_dto(e):
    return {
        "id": str(e.id),
        "kind": e.kind,
        "source_id": str(e.source_id),
        "prescription_id": str(e.prescription_id) if e.prescription_id else None,
        "patient_id": str(e.patient_id),
        "drug_id": str(e.drug_id),
        "drug_name": e.drug_name,
        "class_code": e.class_code,
        "quantity": float(e.quantity),
        "days_supply": e.days_supply,
        "start_date": e.start_date,
        "end_date": e.end_date,
        "daily_mme": float(e.daily_mme),
        "prescriber_key": e.prescriber_key,
        "prescriber_name": e.prescriber_name,
        "facility_id": str(e.facility_id) if e.facility_id else None,
        "facility_name": e.facility_name,
        "sub_county": e.sub_county,
        "is_paper": e.is_paper,
        "status": e.status,
        "occurred_at": e.occurred_at,
    }


def get_supply_window(patient_id, as_of=None, days=120):
    """Active events for a patient over the look-back window. Used by the Alerts engine."""
    as_of = as_of or timezone.localdate()
    qs = MedicationEvent.objects.filter(
        patient_id=patient_id, status="ACTIVE", start_date__gte=as_of - timedelta(days=days), start_date__lte=as_of
    ).order_by("start_date")
    return [event_dto(e) for e in qs]


def get_timeline(patient_id, date_from=None, date_to=None, class_code=None):
    qs = MedicationEvent.objects.filter(patient_id=patient_id)
    if date_from:
        qs = qs.filter(start_date__gte=date_from)
    if date_to:
        qs = qs.filter(start_date__lte=date_to)
    if class_code:
        qs = qs.filter(class_code=class_code.upper())
    return [event_dto(e) for e in qs.order_by("-occurred_at")]


def get_summary(patient_id, as_of=None):
    as_of = as_of or timezone.localdate()
    since = as_of - timedelta(days=90)
    recent = MedicationEvent.objects.filter(patient_id=patient_id, status="ACTIVE", start_date__gte=since)
    active = recent.filter(kind="DISPENSED", end_date__gt=as_of)
    return {
        "as_of": as_of,
        "active_medicines": [
            {
                "drug_name": e.drug_name,
                "class_code": e.class_code,
                "quantity": float(e.quantity),
                "start_date": e.start_date,
                "end_date": e.end_date,
                "days_left": (e.end_date - as_of).days,
                "daily_mme": float(e.daily_mme),
                "facility_name": e.facility_name,
                "prescriber_name": e.prescriber_name,
            }
            for e in active.order_by("end_date")
        ],
        "total_daily_mme": float(active.filter(class_code="OPIOID").aggregate(s=Sum("daily_mme"))["s"] or 0),
        "prescribers_90d": recent.exclude(prescriber_key="").values("prescriber_key").distinct().count(),
        "pharmacies_90d": recent.filter(kind="DISPENSED").values("facility_id").distinct().count(),
        "dispenses_90d": recent.filter(kind="DISPENSED").count(),
        "last_dispense": recent.filter(kind="DISPENSED").order_by("-occurred_at").values_list("occurred_at", flat=True).first(),
    }


# ---- Aggregates for the Oversight module -------------------------------------------------------

def _dispensed(county_code, date_from, date_to):
    return MedicationEvent.objects.filter(
        kind="DISPENSED", status="ACTIVE", county_code=county_code, start_date__gte=date_from, start_date__lte=date_to
    )


def dispense_totals(county_code, date_from, date_to):
    qs = _dispensed(county_code, date_from, date_to)
    return {
        "dispenses": qs.count(),
        "patients": qs.values("patient_id").distinct().count(),
        "prescriptions": MedicationEvent.objects.filter(
            kind="PRESCRIBED", county_code=county_code, start_date__gte=date_from, start_date__lte=date_to
        ).count(),
        "paper_dispenses": qs.filter(is_paper=True).count(),
        "by_class": list(qs.values("class_code").annotate(dispenses=Count("id"), quantity=Sum("quantity")).order_by("-dispenses")),
    }


def weekly_trend(county_code, date_from, date_to):
    rows = (
        _dispensed(county_code, date_from, date_to)
        .annotate(week=TruncWeek("start_date"))
        .values("week", "class_code")
        .annotate(n=Count("id"))
        .order_by("week")
    )
    weeks = defaultdict(dict)
    for r in rows:
        week = r["week"].date() if hasattr(r["week"], "date") else r["week"]
        weeks[week][r["class_code"]] = r["n"]
    return [{"week": w, **counts} for w, counts in sorted(weeks.items())]


def prescriber_stats(county_code, date_from, date_to):
    qs = MedicationEvent.objects.filter(
        kind="PRESCRIBED", status__in=["ACTIVE"], county_code=county_code, start_date__gte=date_from, start_date__lte=date_to
    ).exclude(prescriber_key="")
    rows = qs.values("prescriber_key", "prescriber_name", "facility_name").annotate(
        prescriptions=Count("id"), patients=Count("patient_id", distinct=True), quantity=Sum("quantity")
    )
    stats = {}
    for r in rows:  # one prescriber may appear at several facilities; merge
        s = stats.get(r["prescriber_key"])
        if s is None:
            s = stats[r["prescriber_key"]] = {
                "prescriber_name": r["prescriber_name"], "prescriptions": 0, "patients": 0, "quantity": 0, "facilities": set()
            }
        s["prescriptions"] += r["prescriptions"]
        s["patients"] += r["patients"]
        s["quantity"] += float(r["quantity"] or 0)
        s["facilities"].add(r["facility_name"])
    opioid = dict(
        qs.filter(class_code="OPIOID").values("prescriber_key").annotate(n=Count("id")).values_list("prescriber_key", "n")
    )
    out = []
    for key, s in stats.items():
        out.append({
            "prescriber_key": key,
            "prescriber_name": s["prescriber_name"],
            "facilities": sorted(f for f in s["facilities"] if f),
            "prescriptions": s["prescriptions"],
            "opioid_prescriptions": opioid.get(key, 0),
            "patients": s["patients"],
            "quantity": float(s["quantity"] or 0),
        })
    return out


def pharmacy_stats(county_code, date_from, date_to):
    rows = (
        _dispensed(county_code, date_from, date_to)
        .values("facility_id", "facility_name", "sub_county")
        .annotate(dispenses=Count("id"), patients=Count("patient_id", distinct=True), quantity=Sum("quantity"))
    )
    paper = dict(
        _dispensed(county_code, date_from, date_to).filter(is_paper=True)
        .values("facility_id").annotate(n=Count("id")).values_list("facility_id", "n")
    )
    return [
        {
            "facility_id": str(r["facility_id"]),
            "facility_name": r["facility_name"],
            "sub_county": r["sub_county"],
            "dispenses": r["dispenses"],
            "patients": r["patients"],
            "quantity": float(r["quantity"] or 0),
            "paper_dispenses": paper.get(r["facility_id"], 0),
        }
        for r in rows
    ]


def sub_county_stats(county_code, date_from, date_to):
    rows = (
        _dispensed(county_code, date_from, date_to)
        .values("sub_county")
        .annotate(dispenses=Count("id"), patients=Count("patient_id", distinct=True), quantity=Sum("quantity"))
    )
    return [{**r, "quantity": float(r["quantity"] or 0)} for r in rows]


def dispensed_quantity_by_facility_drug(county_code, date_from, date_to):
    rows = (
        _dispensed(county_code, date_from, date_to)
        .values("facility_id", "facility_name", "drug_id", "drug_name")
        .annotate(quantity=Sum("quantity"))
    )
    return [{**r, "facility_id": str(r["facility_id"]), "drug_id": str(r["drug_id"]), "quantity": float(r["quantity"])} for r in rows]
