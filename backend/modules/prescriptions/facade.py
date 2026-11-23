"""Public interface of the Prescription module."""
from . import services


def get_dispensable_state(prescription_id=None, code=None, now=None):
    """Everything Dispensing needs to decide whether (and how much) can be dispensed (as at `now`)."""
    rx = services.find(prescription_id=prescription_id, code=code, now=now)
    if not rx:
        return None
    return {
        "id": str(rx.id),
        "code": rx.code,
        "patient_id": str(rx.patient_id),
        "drug_id": str(rx.drug_id),
        "quantity": float(rx.quantity),
        "days_supply": rx.days_supply,
        "refills_allowed": rx.refills_allowed,
        "quantity_dispensed": float(rx.quantity_dispensed),
        "remaining_quantity": float(rx.remaining_quantity),
        "status": rx.status,
        "expires_at": rx.expires_at,
        "prescriber_id": str(rx.prescriber_id),
        "prescriber_name": rx.prescriber_name,
        "prescriber_licence": rx.prescriber_licence,
        "facility_id": str(rx.facility_id),
        "dosage_instructions": rx.dosage_instructions,
    }
