"""Builds the medication timeline from Prescription and Dispensing events."""
from datetime import date, datetime, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.events import subscribe
from modules.registry import facade as registry

from .models import MedicationEvent


def _dt(value):
    return value if isinstance(value, datetime) else parse_datetime(value)


def _upsert(kind, source_id, payload, occurred_at):
    drug = registry.get_drug(payload["drug_id"])
    facility = registry.get_facility(payload["facility_id"]) if payload.get("facility_id") else None
    occurred = _dt(occurred_at)
    start = timezone.localtime(occurred).date() if isinstance(occurred, datetime) else date.fromisoformat(str(occurred)[:10])
    days = int(payload["days_supply"])
    MedicationEvent.objects.update_or_create(
        kind=kind,
        source_id=source_id,
        defaults={
            "prescription_id": payload.get("prescription_id"),
            "patient_id": payload["patient_id"],
            "drug_id": payload["drug_id"],
            "drug_name": drug["name"] if drug else "Unknown drug",
            "class_code": drug["class_code"] if drug else "UNKNOWN",
            "quantity": payload["quantity"],
            "days_supply": days,
            "start_date": start,
            "end_date": start + timedelta(days=days),
            "daily_mme": registry.daily_mme(drug, payload["quantity"], days),
            "prescriber_key": payload.get("prescriber_key", ""),
            "prescriber_name": payload.get("prescriber_name", ""),
            "facility_id": payload.get("facility_id"),
            "facility_name": facility["name"] if facility else "",
            "sub_county": facility["sub_county"] if facility else "",
            "is_paper": bool(payload.get("is_paper")),
            "county_code": payload.get("county_code") or (facility["county_code"] if facility else "047"),
            "occurred_at": occurred,
        },
    )


def on_prescription_created(p):
    _upsert(MedicationEvent.Kind.PRESCRIBED, p["prescription_id"], p, p["issued_at"])


def on_prescription_cancelled(p):
    MedicationEvent.objects.filter(kind="PRESCRIBED", source_id=p["prescription_id"]).update(status="CANCELLED")


def on_dispense_recorded(p):
    _upsert(MedicationEvent.Kind.DISPENSED, p["dispense_id"], p, p["dispensed_at"])


def on_dispense_voided(p):
    MedicationEvent.objects.filter(kind="DISPENSED", source_id=p["dispense_id"]).update(status="VOIDED")


def register():
    subscribe("PrescriptionCreated", on_prescription_created)
    subscribe("PrescriptionCancelled", on_prescription_cancelled)
    subscribe("DispenseRecorded", on_dispense_recorded)
    subscribe("DispenseVoided", on_dispense_voided)
