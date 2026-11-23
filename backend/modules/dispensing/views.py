from decimal import Decimal

from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import DomainError
from core.serializers import AckSerializer
from core.permissions import Roles, RequiresPurposeOfUse, actor_of, has_role
from modules.audit import facade as audit
from modules.registry import facade as registry

from . import services
from .models import Dispense


class DispenseInputSerializer(serializers.Serializer):
    # Either an e-prescription (id or code) ...
    prescription_id = serializers.UUIDField(required=False, allow_null=True)
    prescription_code = serializers.CharField(required=False, allow_blank=True)
    # ... or a paper prescription
    patient_id = serializers.UUIDField(required=False, allow_null=True)
    drug_id = serializers.UUIDField(required=False, allow_null=True)
    days_supply = serializers.IntegerField(required=False, min_value=1, max_value=180)
    paper_prescriber_name = serializers.CharField(required=False, allow_blank=True)
    paper_prescriber_licence = serializers.CharField(required=False, allow_blank=True)
    paper_prescriber_facility = serializers.CharField(required=False, allow_blank=True)
    paper_rx_date = serializers.DateField(required=False, allow_null=True)
    paper_rx_number = serializers.CharField(required=False, allow_blank=True)
    # Common
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    batch_number = serializers.CharField(required=False, allow_blank=True)


class DispenseCommitSerializer(DispenseInputSerializer):
    evaluation_id = serializers.UUIDField(required=False, allow_null=True)
    acknowledgements = AckSerializer(many=True, required=False, default=list)


class DispenseSerializer(serializers.ModelSerializer):
    drug = serializers.SerializerMethodField()
    facility = serializers.SerializerMethodField()

    class Meta:
        model = Dispense
        fields = [
            "id", "patient_id", "prescription_id", "drug_id", "drug", "quantity", "days_supply", "batch_number",
            "facility_id", "facility", "pharmacist_id", "pharmacist_name", "prescriber_name", "prescriber_licence",
            "is_paper", "paper_rx_date", "paper_rx_number", "paper_prescriber_facility", "paper_licence_verified",
            "dispensed_at", "status", "void_reason", "voided_at",
        ]

    def get_drug(self, obj):
        return registry.get_drug(obj.drug_id)

    def get_facility(self, obj):
        return registry.get_facility(obj.facility_id)


PHARMACIST_PERMS = [IsAuthenticated, has_role(Roles.PHARMACIST), RequiresPurposeOfUse]


class DispensePreviewView(APIView):
    permission_classes = PHARMACIST_PERMS

    def post(self, request):
        ser = DispenseInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(services.preview(ser.validated_data, actor_of(request)))


class DispenseCreateView(APIView):
    permission_classes = PHARMACIST_PERMS

    def post(self, request):
        ser = DispenseCommitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        d = services.commit(
            data, actor_of(request),
            acknowledgements=data.get("acknowledgements"),
            evaluation_id=data.get("evaluation_id"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        return Response(DispenseSerializer(d).data, status=status.HTTP_201_CREATED)


class DispenseDetailView(APIView):
    permission_classes = [IsAuthenticated, has_role(Roles.PHARMACIST, Roles.REGULATOR), RequiresPurposeOfUse]

    def get(self, request, dispense_id):
        d = Dispense.objects.filter(id=dispense_id).first()
        if not d:
            raise DomainError("DISPENSE_NOT_FOUND", "Dispense not found.", 404)
        audit.record(action="READ", resource_type="Dispense", resource_id=d.id, actor=actor_of(request), patient_id=d.patient_id)
        return Response(DispenseSerializer(d).data)


class DispenseVoidView(APIView):
    permission_classes = PHARMACIST_PERMS

    def post(self, request, dispense_id):
        d = services.void(dispense_id, actor_of(request), request.data.get("reason", ""))
        return Response(DispenseSerializer(d).data)


class FacilityDispensesView(generics.ListAPIView):
    """Facility dispensing register. Pharmacists see their own facility; regulators any facility in their county."""

    serializer_class = DispenseSerializer
    permission_classes = [IsAuthenticated, has_role(Roles.PHARMACIST, Roles.REGULATOR)]

    def get_queryset(self):
        user, fid = self.request.user, self.kwargs["facility_id"]
        if user.role == Roles.PHARMACIST and str(user.facility_id) != str(fid):
            raise DomainError("OUT_OF_SCOPE", "You can only view your own facility's register.", 403)
        qs = Dispense.objects.filter(facility_id=fid, county_code=user.county_code)
        p = self.request.query_params
        if v := p.get("from"):
            qs = qs.filter(dispensed_at__date__gte=v)
        if v := p.get("to"):
            qs = qs.filter(dispensed_at__date__lte=v)
        return qs
