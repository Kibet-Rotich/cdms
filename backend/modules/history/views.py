from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import Roles, RequiresPurposeOfUse, actor_of, has_role
from modules.audit import facade as audit

from . import facade

PERMS = [IsAuthenticated, has_role(Roles.PRESCRIBER, Roles.PHARMACIST, Roles.REGULATOR), RequiresPurposeOfUse]


class MedicationHistoryView(APIView):
    permission_classes = PERMS

    def get(self, request, patient_id):
        p = request.query_params
        items = facade.get_timeline(patient_id, p.get("from"), p.get("to"), p.get("class"))
        audit.record(action="READ", resource_type="MedicationHistory", resource_id=patient_id, actor=actor_of(request), patient_id=patient_id)
        return Response({"items": items, "total": len(items)})


class MedicationSummaryView(APIView):
    permission_classes = PERMS

    def get(self, request, patient_id):
        audit.record(action="READ", resource_type="MedicationSummary", resource_id=patient_id, actor=actor_of(request), patient_id=patient_id)
        return Response(facade.get_summary(patient_id))
