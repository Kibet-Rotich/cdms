"""Dispensing use cases. Hard checks (FR-E4) block; alert rules are advisory and need acknowledgement."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.events import publish
from core.exceptions import DomainError
from modules.alerts import facade as alerts
from modules.patients import facade as patients
from modules.prescriptions import facade as prescriptions
from modules.registry import facade as registry

from .models import Dispense


def _require_pharmacist(actor):
    if actor["role"] != "PHARMACIST":
        raise DomainError("FORBIDDEN", "Only pharmacists can dispense.", 403)
    if not actor.get("facility_id"):
        raise DomainError("NO_FACILITY", "Your account is not linked to a facility.")


def build_proposal(data, actor, now=None):
    """Validate the request and return (patient_id, proposal, context). Raises on hard-rule violations."""
    _require_pharmacist(actor)
    quantity = Decimal(str(data["quantity"]))
    if quantity <= 0:
        raise DomainError("INVALID_QUANTITY", "Quantity must be positive.")

    rx_ref = data.get("prescription_id") or data.get("prescription_code")
    if rx_ref:
        rx = prescriptions.get_dispensable_state(prescription_id=data.get("prescription_id"), code=data.get("prescription_code"), now=now)
        if not rx:
            raise DomainError("PRESCRIPTION_NOT_FOUND", "Prescription not found.", 404)
        # ---- Hard rules (blocking) ----
        if rx["status"] == "COMPLETED" or rx["remaining_quantity"] <= 0:
            raise DomainError("PRESCRIPTION_ALREADY_DISPENSED",
                              f"Prescription {rx['code']} has already been fully dispensed and cannot be dispensed again.", 409,
                              {"prescription": rx})
        if rx["status"] in ("CANCELLED", "EXPIRED"):
            raise DomainError(f"PRESCRIPTION_{rx['status']}", f"Prescription {rx['code']} is {rx['status'].lower()}.", 409, {"prescription": rx})
        if data.get("patient_id") and str(data["patient_id"]) != rx["patient_id"]:
            raise DomainError("PATIENT_MISMATCH", "This prescription belongs to a different patient.", 409)
        max_now = min(rx["remaining_quantity"], rx["quantity"])
        if float(quantity) > max_now:
            raise DomainError("QUANTITY_EXCEEDS_PRESCRIPTION", f"At most {max_now:g} units can be dispensed on this fill.", 409)
        days = max(1, round(rx["days_supply"] * float(quantity) / rx["quantity"]))
        patient_id = rx["patient_id"]
        proposal = {
            "drug_id": rx["drug_id"], "quantity": float(quantity), "days_supply": days,
            "prescriber_key": rx["prescriber_licence"], "prescriber_name": rx["prescriber_name"],
            "facility_id": actor["facility_id"], "prescription_id": rx["id"], "is_paper": False,
            "paper_licence_verified": True,
        }
        context = {"prescription": rx, "drug_id": rx["drug_id"]}
    else:
        # ---- Paper prescription ----
        required = ["patient_id", "drug_id", "days_supply", "paper_prescriber_name", "paper_prescriber_licence", "paper_rx_date"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise DomainError("MISSING_FIELDS", f"Paper prescription requires: {', '.join(missing)}.")
        drug = registry.get_drug(data["drug_id"])
        if not drug or not drug["monitored"]:
            raise DomainError("DRUG_NOT_MONITORED", "Drug not found in the monitored catalogue.", 404)
        licence = data["paper_prescriber_licence"].strip().upper()
        practitioner = registry.verify_practitioner(licence)
        verified = bool(practitioner and practitioner["status"] == "ACTIVE" and practitioner["role_group"] == "PRESCRIBER")
        patient_id = str(data["patient_id"])
        proposal = {
            "drug_id": str(data["drug_id"]), "quantity": float(quantity), "days_supply": int(data["days_supply"]),
            "prescriber_key": licence, "prescriber_name": practitioner["full_name"] if verified else data["paper_prescriber_name"],
            "facility_id": actor["facility_id"], "prescription_id": None, "is_paper": True,
            "paper_licence_verified": verified,
        }
        context = {"prescription": None, "drug_id": str(data["drug_id"])}

    if not patients.get_patient(patient_id):
        raise DomainError("PATIENT_NOT_FOUND", "Patient not found.", 404)
    return patient_id, proposal, context


def preview(data, actor, as_of=None):
    patient_id, proposal, context = build_proposal(data, actor)
    result = alerts.evaluate(action="DISPENSE", patient_id=patient_id, proposed=proposal, actor=actor, as_of=as_of)
    result["prescription"] = context["prescription"]
    result["patient_id"] = patient_id
    return result


def commit(data, actor, *, acknowledgements=None, evaluation_id=None, idempotency_key=None, dispensed_at=None):
    if idempotency_key:
        existing = Dispense.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
    dispensed_at = dispensed_at or timezone.now()
    patient_id, proposal, context = build_proposal(data, actor, now=dispensed_at)
    as_of = timezone.localtime(dispensed_at).date()
    with transaction.atomic():
        findings = alerts.confirm(
            action="DISPENSE", patient_id=patient_id, proposed=proposal, acknowledgements=acknowledgements,
            evaluation_id=evaluation_id, as_of=as_of,
        )
        d = Dispense.objects.create(
            patient_id=patient_id,
            prescription_id=proposal["prescription_id"],
            drug_id=proposal["drug_id"],
            quantity=proposal["quantity"],
            days_supply=proposal["days_supply"],
            batch_number=data.get("batch_number", "") or "",
            facility_id=actor["facility_id"],
            pharmacist_id=actor["id"],
            pharmacist_name=actor["full_name"],
            prescriber_name=proposal["prescriber_name"],
            prescriber_licence=proposal["prescriber_key"],
            is_paper=proposal["is_paper"],
            paper_rx_date=data.get("paper_rx_date") if proposal["is_paper"] else None,
            paper_rx_number=data.get("paper_rx_number", "") if proposal["is_paper"] else "",
            paper_prescriber_facility=data.get("paper_prescriber_facility", "") if proposal["is_paper"] else "",
            paper_licence_verified=proposal["paper_licence_verified"],
            dispensed_at=dispensed_at,
            evaluation_id=evaluation_id,
            idempotency_key=idempotency_key,
            county_code=actor["county_code"],
        )
        alerts.record(
            findings=findings, acknowledgements=acknowledgements, action="DISPENSE", subject_type="Dispense",
            subject_id=d.id, patient_id=patient_id, facility_id=actor["facility_id"], prescriber_key=proposal["prescriber_key"],
            actor=actor, occurred_at=dispensed_at, county_code=d.county_code, evaluation_id=evaluation_id,
        )
        publish("DispenseRecorded", {
            "dispense_id": d.id, "prescription_id": d.prescription_id, "patient_id": d.patient_id, "drug_id": d.drug_id,
            "quantity": d.quantity, "days_supply": d.days_supply, "dispensed_at": d.dispensed_at,
            "prescriber_key": d.prescriber_licence, "prescriber_name": d.prescriber_name, "facility_id": d.facility_id,
            "pharmacist_id": d.pharmacist_id, "county_code": d.county_code, "is_paper": d.is_paper,
            "batch_number": d.batch_number, "actor_id": actor["id"], "alerts": [f["rule_code"] for f in findings],
        })
    return d


def void(dispense_id, actor, reason):
    _require_pharmacist(actor)
    d = Dispense.objects.filter(id=dispense_id).first()
    if not d:
        raise DomainError("DISPENSE_NOT_FOUND", "Dispense not found.", 404)
    if str(d.facility_id) != actor["facility_id"]:
        raise DomainError("OUT_OF_SCOPE", "You can only void dispenses made at your facility.", 403)
    if d.status == Dispense.Status.VOIDED:
        raise DomainError("ALREADY_VOIDED", "This dispense is already voided.", 409)
    if not (reason or "").strip():
        raise DomainError("REASON_REQUIRED", "A reason is required to void a dispense.")
    with transaction.atomic():
        d.status = Dispense.Status.VOIDED
        d.void_reason = reason
        d.voided_by = actor["id"]
        d.voided_at = timezone.now()
        d.save()
        publish("DispenseVoided", {
            "dispense_id": d.id, "prescription_id": d.prescription_id, "patient_id": d.patient_id,
            "quantity": d.quantity, "actor_id": actor["id"], "reason": reason,
        })
    return d
