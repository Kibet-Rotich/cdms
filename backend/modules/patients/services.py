"""Patient use cases: find (local, then Client Registry), register, duplicate detection."""
from django.db import transaction

from core.events import publish
from core.exceptions import DomainError
from modules.interop import facade as interop

from .models import Patient, PatientIdentifier


def normalise(value):
    return (value or "").strip().upper().replace(" ", "")


def find_by_identifier(id_type, value):
    """Return (patient, source) where source is LOCAL or CLIENT_REGISTRY; (None, None) if not found."""
    id_type, value = id_type.upper(), normalise(value)
    ident = PatientIdentifier.objects.select_related("patient").filter(id_type=id_type, value=value).first()
    if ident:
        return ident.patient, "LOCAL"

    record = interop.lookup_client(id_type, value)
    if not record:
        return None, None
    with transaction.atomic():
        patient = Patient.objects.filter(cr_id=record["cr_id"]).first() if record.get("cr_id") else None
        if patient is None:
            patient = Patient.objects.create(
                cr_id=record.get("cr_id", ""),
                first_name=record["first_name"],
                middle_name=record.get("middle_name", ""),
                last_name=record["last_name"],
                date_of_birth=record["date_of_birth"],
                sex=record["sex"],
                phone=record.get("phone", ""),
                verified=True,
            )
        PatientIdentifier.objects.get_or_create(patient=patient, id_type=id_type, value=value)
        publish("PatientLinkedFromRegistry", {"patient_id": patient.id, "cr_id": patient.cr_id})
    return patient, "CLIENT_REGISTRY"


def possible_duplicates(first_name, last_name, date_of_birth, phone="", exclude_id=None):
    qs = Patient.objects.filter(
        first_name__iexact=first_name.strip(), last_name__iexact=last_name.strip(), date_of_birth=date_of_birth
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    matches = list(qs[:10])
    if phone:
        matches += [p for p in Patient.objects.filter(phone=phone).exclude(id=exclude_id)[:10] if p not in matches]
    return matches


@transaction.atomic
def register(data, actor):
    id_type, value = data["id_type"].upper(), normalise(data["id_number"])
    if PatientIdentifier.objects.filter(id_type=id_type, value=value).exists():
        raise DomainError("PATIENT_EXISTS", "A patient with this identifier already exists.", 409)
    patient = Patient.objects.create(
        first_name=data["first_name"].strip(),
        middle_name=data.get("middle_name", "").strip(),
        last_name=data["last_name"].strip(),
        date_of_birth=data["date_of_birth"],
        sex=data["sex"],
        phone=data.get("phone", ""),
        verified=False,
        registered_by=actor["id"],
        registered_at_facility=actor.get("facility_id"),
        county_code=actor.get("county_code") or Patient._meta.get_field("county_code").get_default(),
    )
    PatientIdentifier.objects.create(patient=patient, id_type=id_type, value=value)
    publish("PatientRegistered", {"patient_id": patient.id, "actor_id": actor["id"], "verified": False})
    return patient
