from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import DomainError
from core.permissions import Roles, RequiresPurposeOfUse, actor_of, has_role
from modules.audit import facade as audit

from . import services
from .facade import get_patient, patient_dto
from .models import Patient, PatientIdentifier

CLINICAL_OR_REGULATOR = has_role(Roles.PRESCRIBER, Roles.PHARMACIST, Roles.REGULATOR)


class PatientCreateSerializer(serializers.Serializer):
    id_type = serializers.ChoiceField(choices=PatientIdentifier.IdType.choices)
    id_number = serializers.CharField(max_length=40)
    first_name = serializers.CharField(max_length=60)
    middle_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=60)
    date_of_birth = serializers.DateField()
    sex = serializers.ChoiceField(choices=Patient.Sex.choices)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


class PatientSearchView(APIView):
    """GET /patients/search?idType=NATIONAL_ID&idNumber=12345678 (local first, then Client Registry)."""

    permission_classes = [IsAuthenticated, has_role(*Roles.CLINICAL), RequiresPurposeOfUse]

    def get(self, request):
        id_type = request.query_params.get("idType", "")
        id_number = request.query_params.get("idNumber", "")
        if id_type.upper() not in PatientIdentifier.IdType.values or not id_number.strip():
            raise DomainError("INVALID_IDENTIFIER", "Provide a valid idType and idNumber.")
        patient, source = services.find_by_identifier(id_type, id_number)
        actor = actor_of(request)
        audit.record(
            action="SEARCH", resource_type="Patient", resource_id=patient.id if patient else "",
            actor=actor, patient_id=patient.id if patient else None,
            details={"id_type": id_type.upper(), "found": bool(patient), "source": source},
        )
        if not patient:
            raise DomainError("PATIENT_NOT_FOUND", "No patient found locally or in the Client Registry.", 404)
        return Response({"source": source, "patient": get_patient(patient.id)})


class PatientCreateView(APIView):
    permission_classes = [IsAuthenticated, has_role(*Roles.CLINICAL), RequiresPurposeOfUse]

    def post(self, request):
        ser = PatientCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        dupes = services.possible_duplicates(data["first_name"], data["last_name"], data["date_of_birth"], data.get("phone", ""))
        if dupes and not request.query_params.get("confirm") == "true":
            raise DomainError(
                "POSSIBLE_DUPLICATE",
                "Patients with matching details already exist. Check them, or resubmit with ?confirm=true.",
                409,
                {"candidates": [patient_dto(p) for p in dupes]},
            )
        patient = services.register(data, actor_of(request))
        return Response(get_patient(patient.id), status=status.HTTP_201_CREATED)


class PatientDetailView(APIView):
    permission_classes = [IsAuthenticated, CLINICAL_OR_REGULATOR, RequiresPurposeOfUse]

    def get(self, request, patient_id):
        patient = get_patient(patient_id)
        if not patient:
            raise DomainError("PATIENT_NOT_FOUND", "Patient not found.", 404)
        audit.record(action="READ", resource_type="Patient", resource_id=patient_id, actor=actor_of(request), patient_id=patient_id)
        return Response(patient)


class PatientDuplicatesView(APIView):
    permission_classes = [IsAuthenticated, CLINICAL_OR_REGULATOR, RequiresPurposeOfUse]

    def get(self, request, patient_id):
        p = Patient.objects.filter(id=patient_id).first()
        if not p:
            raise DomainError("PATIENT_NOT_FOUND", "Patient not found.", 404)
        dupes = services.possible_duplicates(p.first_name, p.last_name, p.date_of_birth, p.phone, exclude_id=p.id)
        return Response([patient_dto(d) for d in dupes])
