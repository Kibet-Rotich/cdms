from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import Roles, has_role

from .facade import verify_chain
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "seq", "occurred_at", "actor_id", "actor_name", "actor_role", "facility_id", "action",
            "resource_type", "resource_id", "patient_id", "purpose", "ip_address", "details", "hash",
        ]


class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer
    permission_classes = [has_role(Roles.SYSTEM_ADMIN, Roles.REGULATOR)]

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        p = self.request.query_params
        if v := p.get("actorId"):
            qs = qs.filter(actor_id=v)
        if v := p.get("patientId"):
            qs = qs.filter(patient_id=v)
        if v := p.get("action"):
            qs = qs.filter(action__icontains=v)
        if v := p.get("from"):
            qs = qs.filter(occurred_at__date__gte=v)
        if v := p.get("to"):
            qs = qs.filter(occurred_at__date__lte=v)
        if p.get("accessOnly") == "true":
            qs = qs.exclude(action__startswith="EVENT:")
        return qs


class AuditVerifyView(APIView):
    permission_classes = [has_role(Roles.SYSTEM_ADMIN, Roles.REGULATOR)]

    def get(self, request):
        ok, broken = verify_chain()
        return Response({"intact": ok, "firstBrokenSeq": broken, "events": AuditEvent.objects.count()})
