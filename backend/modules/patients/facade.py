"""Public interface of the Patient module."""
import hashlib

from django.conf import settings

from .models import Patient


def patient_dto(p):
    return {
        "id": str(p.id),
        "cr_id": p.cr_id,
        "full_name": p.full_name,
        "first_name": p.first_name,
        "middle_name": p.middle_name,
        "last_name": p.last_name,
        "date_of_birth": p.date_of_birth.isoformat() if hasattr(p.date_of_birth, "isoformat") else p.date_of_birth,
        "sex": p.sex,
        "phone": p.phone,
        "verified": p.verified,
        "county_code": p.county_code,
        "identifiers": [{"id_type": i.id_type, "value": i.value} for i in p.identifiers.all()],
    }


def get_patient(patient_id):
    p = Patient.objects.prefetch_related("identifiers").filter(id=patient_id).first()
    return patient_dto(p) if p else None


def get_patients_map(patient_ids):
    return {str(p.id): patient_dto(p) for p in Patient.objects.prefetch_related("identifiers").filter(id__in=list(patient_ids))}


def pseudonym(patient_id):
    """Stable pseudonymous reference used on regulator views before identity is revealed."""
    digest = hashlib.sha256(f"{patient_id}:{settings.SECRET_KEY}".encode()).hexdigest()
    return f"P-{digest[:8].upper()}"
