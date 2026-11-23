from decimal import Decimal

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import DomainError
from core.serializers import AckSerializer
from core.permissions import Roles, RequiresPurposeOfUse, actor_of, has_role
from modules.audit import facade as audit
from modules.registry import facade as registry

from . import services
from .models import Prescription


class PrescriptionInputSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    drug_id = serializers.UUIDField()
    dosage_instructions = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    days_supply = serializers.IntegerField(min_value=1, max_value=180)
    refills_allowed = serializers.IntegerField(min_value=0, max_value=5, default=0)
    diagnosis_note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PrescriptionCommitSerializer(PrescriptionInputSerializer):
    evaluation_id = serializers.UUIDField(required=False, allow_null=True)
    acknowledgements = AckSerializer(many=True, required=False, default=list)


class PrescriptionSerializer(serializers.ModelSerializer):
    remaining_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    drug = serializers.SerializerMethodField()
    facility = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            "id", "code", "patient_id", "prescriber_id", "prescriber_name", "prescriber_licence", "facility_id",
            "facility", "drug_id", "drug", "dosage_instructions", "quantity", "days_supply", "refills_allowed",
            "quantity_dispensed", "remaining_quantity", "diagnosis_note", "notes", "status", "issued_at",
            "expires_at", "cancelled_reason",
        ]

    def get_drug(self, obj):
        return registry.get_drug(obj.drug_id)

    def get_facility(self, obj):
        return registry.get_facility(obj.facility_id)


PRESCRIBER_PERMS = [IsAuthenticated, has_role(Roles.PRESCRIBER), RequiresPurposeOfUse]
CLINICAL_PERMS = [IsAuthenticated, has_role(Roles.PRESCRIBER, Roles.PHARMACIST, Roles.REGULATOR), RequiresPurposeOfUse]


class PrescriptionPreviewView(APIView):
    permission_classes = PRESCRIBER_PERMS

    def post(self, request):
        ser = PrescriptionInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(services.preview(ser.validated_data, actor_of(request)))


class PrescriptionCreateView(APIView):
    permission_classes = PRESCRIBER_PERMS

    def post(self, request):
        ser = PrescriptionCommitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        rx = services.create(
            data, actor_of(request),
            acknowledgements=data.get("acknowledgements"),
            evaluation_id=data.get("evaluation_id"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        return Response(PrescriptionSerializer(rx).data, status=status.HTTP_201_CREATED)


class PrescriptionDetailView(APIView):
    permission_classes = CLINICAL_PERMS

    def get(self, request, prescription_id=None, code=None):
        rx = services.find(prescription_id=prescription_id, code=code)
        if not rx:
            raise DomainError("PRESCRIPTION_NOT_FOUND", "Prescription not found.", 404)
        audit.record(action="READ", resource_type="Prescription", resource_id=rx.id, actor=actor_of(request), patient_id=rx.patient_id)
        return Response(PrescriptionSerializer(rx).data)


class PatientPrescriptionsView(APIView):
    permission_classes = CLINICAL_PERMS

    def get(self, request, patient_id):
        qs = Prescription.objects.filter(patient_id=patient_id)
        for rx in qs.filter(status="ACTIVE"):
            services._expire_if_due(rx)
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s.upper())
        audit.record(action="READ", resource_type="PatientPrescriptions", resource_id=patient_id, actor=actor_of(request), patient_id=patient_id)
        return Response(PrescriptionSerializer(qs, many=True).data)


class PrescriptionCancelView(APIView):
    permission_classes = PRESCRIBER_PERMS

    def post(self, request, prescription_id):
        rx = services.cancel(prescription_id, actor_of(request), request.data.get("reason", ""))
        return Response(PrescriptionSerializer(rx).data)
