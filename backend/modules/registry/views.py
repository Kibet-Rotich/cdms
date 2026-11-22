from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import DomainError
from core.permissions import Roles, has_role

from . import facade
from .models import Drug, DrugClass, Facility


class DrugClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrugClass
        fields = ["code", "name", "description"]


class DrugSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="drug_class.name", read_only=True)

    class Meta:
        model = Drug
        fields = [
            "id", "name", "generic_name", "drug_class", "class_name", "strength_mg", "unit",
            "form", "mme_factor", "monitored", "active",
        ]


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = [
            "id", "kmhfl_code", "name", "facility_type", "ownership", "sub_county", "county_code",
            "ppb_licence_number", "latitude", "longitude", "active",
        ]


class AdminWritePermissionMixin:
    """Anyone authenticated can read; only system admins can write."""

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [has_role(Roles.SYSTEM_ADMIN)()]


class DrugClassViewSet(AdminWritePermissionMixin, viewsets.ModelViewSet):
    queryset = DrugClass.objects.all()
    serializer_class = DrugClassSerializer
    pagination_class = None


class DrugViewSet(AdminWritePermissionMixin, viewsets.ModelViewSet):
    serializer_class = DrugSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Drug.objects.select_related("drug_class")
        if c := self.request.query_params.get("class"):
            qs = qs.filter(drug_class_id=c.upper())
        if self.request.query_params.get("monitored") == "true":
            qs = qs.filter(monitored=True)
        if self.request.query_params.get("active") != "all":
            qs = qs.filter(active=True)
        return qs


class FacilityViewSet(AdminWritePermissionMixin, viewsets.ModelViewSet):
    serializer_class = FacilitySerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        # Facility list is public so the registration form can show it.
        if self.action == "list":
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = Facility.objects.filter(active=True)
        if t := self.request.query_params.get("type"):
            qs = qs.filter(facility_type=t.upper())
        if s := self.request.query_params.get("subCounty"):
            qs = qs.filter(sub_county__iexact=s)
        return qs


class VerifyPractitionerView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        licence = request.query_params.get("licence", "")
        result = facade.verify_practitioner(licence)
        if not result:
            raise DomainError("LICENCE_NOT_FOUND", "Licence number not found in the practitioner registry.", 404)
        return Response(result)
