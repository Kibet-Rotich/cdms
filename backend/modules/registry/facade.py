"""Public interface of the Registry module (master data). Returns plain dicts."""
from modules.interop import facade as interop

from .models import Drug, Facility, Practitioner

PRESCRIBER_CADRES = {"MEDICAL_OFFICER", "CLINICAL_OFFICER", "DENTIST", "SPECIALIST"}


def drug_dto(d):
    return {
        "id": str(d.id),
        "name": d.name,
        "generic_name": d.generic_name,
        "class_code": d.drug_class_id,
        "class_name": d.drug_class.name,
        "strength_mg": float(d.strength_mg),
        "unit": d.unit,
        "mme_factor": float(d.mme_factor) if d.mme_factor is not None else None,
        "monitored": d.monitored,
    }


def facility_dto(f):
    return {
        "id": str(f.id),
        "kmhfl_code": f.kmhfl_code,
        "name": f.name,
        "facility_type": f.facility_type,
        "sub_county": f.sub_county,
        "county_code": f.county_code,
    }


def practitioner_dto(p):
    return {
        "licence_number": p.licence_number,
        "full_name": p.full_name,
        "cadre": p.cadre,
        "regulator": p.regulator,
        "status": p.status,
        "role_group": "PRESCRIBER" if p.cadre in PRESCRIBER_CADRES else "PHARMACIST",
    }


def get_drug(drug_id):
    d = Drug.objects.select_related("drug_class").filter(id=drug_id).first()
    return drug_dto(d) if d else None


def get_drugs_map():
    return {str(d.id): drug_dto(d) for d in Drug.objects.select_related("drug_class").all()}


def get_facility(facility_id):
    f = Facility.objects.filter(id=facility_id).first()
    return facility_dto(f) if f else None


def get_facilities_map(county_code=None):
    qs = Facility.objects.all()
    if county_code:
        qs = qs.filter(county_code=county_code)
    return {str(f.id): facility_dto(f) for f in qs}


def verify_practitioner(licence_number):
    """Check the local copy, then the national register via Interop; cache the result locally."""
    licence_number = (licence_number or "").strip().upper()
    if not licence_number:
        return None
    record = interop.lookup_practitioner(licence_number)
    if record:
        p, _ = Practitioner.objects.update_or_create(
            licence_number=licence_number,
            defaults={
                "full_name": record["full_name"],
                "cadre": record["cadre"],
                "regulator": record["regulator"],
                "status": record.get("status", "ACTIVE"),
            },
        )
        return practitioner_dto(p)
    local = Practitioner.objects.filter(licence_number=licence_number).first()
    return practitioner_dto(local) if local else None


def daily_mme(drug, quantity, days_supply):
    """Morphine milligram equivalents per day for a supply of an opioid. 0 for non-opioids."""
    if not drug or drug.get("mme_factor") is None or not days_supply:
        return 0.0
    return round(float(quantity) * drug["strength_mg"] * drug["mme_factor"] / float(days_supply), 1)
