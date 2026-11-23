from django.db import transaction
from django.utils import timezone
from rest_framework import generics, serializers

from core.events import publish
from core.exceptions import DomainError
from core.permissions import Roles, has_role
from modules.registry import facade as registry

from .models import StockReceipt


class StockReceiptSerializer(serializers.ModelSerializer):
    drug = serializers.SerializerMethodField()

    class Meta:
        model = StockReceipt
        fields = ["id", "facility_id", "drug_id", "drug", "batch_number", "gtin", "quantity", "supplier_name", "received_at", "source"]
        read_only_fields = ["id", "facility_id", "source", "drug"]
        extra_kwargs = {"received_at": {"required": False}}

    def get_drug(self, obj):
        return registry.get_drug(obj.drug_id)


class StockReceiptCreateView(generics.CreateAPIView):
    serializer_class = StockReceiptSerializer
    permission_classes = [has_role(Roles.PHARMACIST)]

    def perform_create(self, serializer):
        user = self.request.user
        if not registry.get_drug(serializer.validated_data["drug_id"]):
            raise DomainError("DRUG_NOT_FOUND", "Drug not found.", 404)
        with transaction.atomic():
            r = serializer.save(
                facility_id=user.facility_id, recorded_by=user.id, county_code=user.county_code,
                received_at=serializer.validated_data.get("received_at") or timezone.now(),
            )
            publish("StockReceived", {"id": r.id, "facility_id": r.facility_id, "drug_id": r.drug_id, "quantity": r.quantity, "actor_id": user.id})


class FacilityStockReceiptsView(generics.ListAPIView):
    serializer_class = StockReceiptSerializer
    permission_classes = [has_role(Roles.PHARMACIST, Roles.REGULATOR)]

    def get_queryset(self):
        user, fid = self.request.user, self.kwargs["facility_id"]
        if user.role == Roles.PHARMACIST and str(user.facility_id) != str(fid):
            raise DomainError("OUT_OF_SCOPE", "You can only view your own facility's stock.", 403)
        return StockReceipt.objects.filter(facility_id=fid, county_code=user.county_code)
