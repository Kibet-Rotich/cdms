"""Read-only FHIR R4 façade: shows the data can flow to Kenya's Shared Health Record / HIE."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import DomainError
from core.permissions import Roles, actor_of, has_role
from modules.audit import facade as audit
from modules.history import facade as history
from modules.patients import facade as patients

PERMS = [IsAuthenticated, has_role(Roles.SYSTEM_ADMIN, Roles.REGULATOR)]
ID_SYSTEMS = {
    "NATIONAL_ID": "https://dha.go.ke/fhir/identifier/national-id",
    "MAISHA_NAMBA": "https://dha.go.ke/fhir/identifier/maisha-namba",
    "BIRTH_CERT": "https://dha.go.ke/fhir/identifier/birth-certificate",
    "PASSPORT": "https://dha.go.ke/fhir/identifier/passport",
    "REFUGEE_ID": "https://dha.go.ke/fhir/identifier/refugee-id",
}


def fhir_patient(p):
    return {
        "resourceType": "Patient",
        "id": p["id"],
        "identifier": [{"system": "https://dha.go.ke/fhir/identifier/client-registry", "value": p["cr_id"]}] * bool(p["cr_id"])
        + [{"system": ID_SYSTEMS.get(i["id_type"], i["id_type"]), "value": i["value"]} for i in p["identifiers"]],
        "name": [{"family": p["last_name"], "given": [n for n in [p["first_name"], p["middle_name"]] if n]}],
        "gender": {"F": "female", "M": "male"}.get(p["sex"], "unknown"),
        "birthDate": p["date_of_birth"],
    }


def _bundle(resources):
    return {"resourceType": "Bundle", "type": "searchset", "total": len(resources),
            "entry": [{"resource": r} for r in resources]}


class PatientResource(APIView):
    permission_classes = PERMS

    def get(self, request, patient_id):
        p = patients.get_patient(patient_id)
        if not p:
            raise DomainError("NOT_FOUND", "Patient not found.", 404)
        audit.record(action="READ", resource_type="FHIR:Patient", resource_id=patient_id, actor=actor_of(request), patient_id=patient_id)
        return Response(fhir_patient(p))


class MedicationDispenseSearch(APIView):
    permission_classes = PERMS

    def get(self, request):
        pid = request.query_params.get("patient")
        if not pid:
            raise DomainError("PATIENT_REQUIRED", "Search requires ?patient=<id>.")
        audit.record(action="SEARCH", resource_type="FHIR:MedicationDispense", actor=actor_of(request), patient_id=pid)
        resources = [
            {
                "resourceType": "MedicationDispense",
                "id": e["source_id"],
                "status": "completed" if e["status"] == "ACTIVE" else "entered-in-error",
                "medicationCodeableConcept": {"text": e["drug_name"]},
                "subject": {"reference": f"Patient/{e['patient_id']}"},
                "performer": [{"actor": {"display": e["facility_name"]}}],
                "authorizingPrescription": [{"reference": f"MedicationRequest/{e['prescription_id']}"}] if e["prescription_id"] else [],
                "quantity": {"value": e["quantity"]},
                "daysSupply": {"value": e["days_supply"], "unit": "days"},
                "whenHandedOver": e["occurred_at"],
            }
            for e in history.get_timeline(pid) if e["kind"] == "DISPENSED"
        ]
        return Response(_bundle(resources))


class MedicationRequestSearch(APIView):
    permission_classes = PERMS

    def get(self, request):
        pid = request.query_params.get("patient")
        if not pid:
            raise DomainError("PATIENT_REQUIRED", "Search requires ?patient=<id>.")
        audit.record(action="SEARCH", resource_type="FHIR:MedicationRequest", actor=actor_of(request), patient_id=pid)
        resources = [
            {
                "resourceType": "MedicationRequest",
                "id": e["source_id"],
                "status": {"ACTIVE": "active", "CANCELLED": "cancelled"}.get(e["status"], "unknown"),
                "intent": "order",
                "medicationCodeableConcept": {"text": e["drug_name"]},
                "subject": {"reference": f"Patient/{e['patient_id']}"},
                "requester": {"display": e["prescriber_name"], "identifier": {"value": e["prescriber_key"]}},
                "authoredOn": e["occurred_at"],
                "dispenseRequest": {"quantity": {"value": e["quantity"]}, "expectedSupplyDuration": {"value": e["days_supply"], "unit": "days"}},
            }
            for e in history.get_timeline(pid) if e["kind"] == "PRESCRIBED"
        ]
        return Response(_bundle(resources))
