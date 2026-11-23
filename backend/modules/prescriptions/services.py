"""Prescription use cases: preview (alerts), create, cancel, expire, and dispensability checks."""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.events import publish
from core.exceptions import DomainError
from modules.alerts import facade as alerts
from modules.patients import facade as patients
from modules.registry import facade as registry

from .models import Prescription

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
VALIDITY_DAYS = 30


def new_code():
    while True:
        code = "RX-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(7))
        if not Prescription.objects.filter(code=code).exists():
            return code


def _validate(data, actor):
    if actor["role"] != "PRESCRIBER":
        raise DomainError("FORBIDDEN", "Only prescribers can create prescriptions.", 403)
    if not actor.get("facility_id"):
        raise DomainError("NO_FACILITY", "Your account is not linked to a facility.")
    if not patients.get_patient(data["patient_id"]):
        raise DomainError("PATIENT_NOT_FOUND", "Patient not found.", 404)
    drug = registry.get_drug(data["drug_id"])
    if not drug or not drug["monitored"]:
        raise DomainError("DRUG_NOT_MONITORED", "Drug not found in the monitored catalogue.", 404)
    if Decimal(str(data["quantity"])) <= 0 or int(data["days_supply"]) <= 0:
        raise DomainError("INVALID_QUANTITY", "Quantity and days' supply must be positive.")
    return drug


def _proposal(data, actor):
    return {
        "drug_id": str(data["drug_id"]),
        "quantity": float(data["quantity"]),
        "days_supply": int(data["days_supply"]),
        "prescriber_key": actor["licence_number"],
        "prescriber_name": actor["full_name"],
        "facility_id": actor["facility_id"],
        "prescription_id": None,
        "is_paper": False,
    }


def preview(data, actor, as_of=None):
    _validate(data, actor)
    return alerts.evaluate(action="PRESCRIBE", patient_id=str(data["patient_id"]), proposed=_proposal(data, actor), actor=actor, as_of=as_of)


def create(data, actor, *, acknowledgements=None, evaluation_id=None, idempotency_key=None, issued_at=None):
    if idempotency_key:
        existing = Prescription.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
    _validate(data, actor)
    issued_at = issued_at or timezone.now()
    as_of = timezone.localtime(issued_at).date()
    patient_id = str(data["patient_id"])
    proposal = _proposal(data, actor)
    with transaction.atomic():
        findings = alerts.confirm(
            action="PRESCRIBE", patient_id=patient_id, proposed=proposal,
            acknowledgements=acknowledgements, evaluation_id=evaluation_id, as_of=as_of,
        )
        rx = Prescription.objects.create(
            code=new_code(),
            patient_id=patient_id,
            prescriber_id=actor["id"],
            prescriber_name=actor["full_name"],
            prescriber_licence=actor["licence_number"],
            facility_id=actor["facility_id"],
            drug_id=data["drug_id"],
            dosage_instructions=data["dosage_instructions"],
            quantity=data["quantity"],
            days_supply=data["days_supply"],
            refills_allowed=data.get("refills_allowed", 0),
            diagnosis_note=data.get("diagnosis_note", ""),
            notes=data.get("notes", ""),
            issued_at=issued_at,
            expires_at=issued_at + timedelta(days=VALIDITY_DAYS),
            county_code=actor["county_code"],
            idempotency_key=idempotency_key,
        )
        alerts.record(
            findings=findings, acknowledgements=acknowledgements, action="PRESCRIBE", subject_type="Prescription",
            subject_id=rx.id, patient_id=patient_id, facility_id=actor["facility_id"], prescriber_key=rx.prescriber_licence,
            actor=actor, occurred_at=issued_at, county_code=rx.county_code, evaluation_id=evaluation_id,
        )
        publish("PrescriptionCreated", {
            "prescription_id": rx.id, "code": rx.code, "patient_id": rx.patient_id, "drug_id": rx.drug_id,
            "quantity": rx.quantity, "days_supply": rx.days_supply, "refills_allowed": rx.refills_allowed,
            "issued_at": rx.issued_at, "prescriber_key": rx.prescriber_licence, "prescriber_name": rx.prescriber_name,
            "prescriber_id": rx.prescriber_id, "facility_id": rx.facility_id, "county_code": rx.county_code,
            "actor_id": actor["id"], "alerts": [f["rule_code"] for f in findings],
        })
    return rx


def _expire_if_due(rx, now=None):
    if rx.status == Prescription.Status.ACTIVE and rx.expires_at < (now or timezone.now()):
        with transaction.atomic():
            rx.status = Prescription.Status.EXPIRED
            rx.save(update_fields=["status", "updated_at"])
            publish("PrescriptionExpired", {"prescription_id": rx.id, "patient_id": rx.patient_id})
    return rx


def cancel(prescription_id, actor, reason):
    rx = Prescription.objects.filter(id=prescription_id).first()
    if not rx:
        raise DomainError("PRESCRIPTION_NOT_FOUND", "Prescription not found.", 404)
    if str(rx.prescriber_id) != actor["id"]:
        raise DomainError("FORBIDDEN", "Only the prescriber who wrote this prescription can cancel it.", 403)
    if rx.quantity_dispensed > 0 or rx.status != Prescription.Status.ACTIVE:
        raise DomainError("NOT_CANCELLABLE", "Only active, undispensed prescriptions can be cancelled.", 409)
    with transaction.atomic():
        rx.status = Prescription.Status.CANCELLED
        rx.cancelled_reason = reason or ""
        rx.save(update_fields=["status", "cancelled_reason", "updated_at"])
        publish("PrescriptionCancelled", {"prescription_id": rx.id, "patient_id": rx.patient_id, "actor_id": actor["id"], "reason": reason})
    return rx


def find(prescription_id=None, code=None, now=None):
    qs = Prescription.objects.all()
    rx = qs.filter(id=prescription_id).first() if prescription_id else qs.filter(code=(code or "").strip().upper()).first()
    return _expire_if_due(rx, now) if rx else None


# ---- Event handlers (subscribed in apps.py) -----------------------------------------------------

def on_dispense_recorded(payload):
    if not payload.get("prescription_id"):
        return
    rx = Prescription.objects.select_for_update().filter(id=payload["prescription_id"]).first()
    if not rx:
        return
    rx.quantity_dispensed += Decimal(str(payload["quantity"]))
    if rx.remaining_quantity <= 0:
        rx.status = Prescription.Status.COMPLETED
    rx.save(update_fields=["quantity_dispensed", "status", "updated_at"])


def on_dispense_voided(payload):
    if not payload.get("prescription_id"):
        return
    rx = Prescription.objects.select_for_update().filter(id=payload["prescription_id"]).first()
    if not rx:
        return
    rx.quantity_dispensed = max(rx.quantity_dispensed - Decimal(str(payload["quantity"])), Decimal(0))
    if rx.status == Prescription.Status.COMPLETED and rx.remaining_quantity > 0:
        rx.status = Prescription.Status.ACTIVE
    rx.save(update_fields=["quantity_dispensed", "status", "updated_at"])
