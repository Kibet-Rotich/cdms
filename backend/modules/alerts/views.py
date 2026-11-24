from django.db import transaction
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.events import publish
from core.exceptions import DomainError
from core.permissions import Roles, actor_of, has_role, purpose_of

from . import facade
from .models import Alert, RuleConfig
from .rules import RULES_BY_CODE


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            "id", "action", "subject_type", "subject_id", "patient_id", "facility_id", "prescriber_key",
            "rule_code", "severity", "title", "message", "details", "acknowledged_by", "acknowledged_by_name",
            "ack_reason", "ack_note", "referral_made", "referral_note", "occurred_at",
        ]


class AlertListView(generics.ListAPIView):
    """Regulators/admins can search all alerts; clinicians only for a specific patient (with purpose of use)."""

    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user, p = self.request.user, self.request.query_params
        qs = Alert.objects.filter(county_code=user.county_code)
        if user.role in Roles.CLINICAL:
            if not p.get("patientId") or not purpose_of(self.request):
                raise DomainError("PATIENT_REQUIRED", "Clinicians must filter by patientId and send X-Purpose-Of-Use.", 403)
        elif user.role not in (Roles.REGULATOR, Roles.SYSTEM_ADMIN):
            raise DomainError("FORBIDDEN", "Not allowed.", 403)
        if v := p.get("patientId"):
            qs = qs.filter(patient_id=v)
        if v := p.get("facilityId"):
            qs = qs.filter(facility_id=v)
        if v := p.get("prescriberKey"):
            qs = qs.filter(prescriber_key=v)
        if v := p.get("severity"):
            qs = qs.filter(severity=v.upper())
        if v := p.get("rule"):
            qs = qs.filter(rule_code=v.upper())
        if v := p.get("from"):
            qs = qs.filter(occurred_at__date__gte=v)
        if v := p.get("to"):
            qs = qs.filter(occurred_at__date__lte=v)
        return qs


class AlertDetailView(generics.RetrieveAPIView):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "alert_id"

    def get_queryset(self):
        return Alert.objects.filter(county_code=self.request.user.county_code)


class AlertReferralView(APIView):
    permission_classes = [has_role(Roles.PRESCRIBER, Roles.PHARMACIST)]

    def post(self, request, alert_id):
        alert = Alert.objects.filter(id=alert_id).first()
        if not alert:
            raise DomainError("ALERT_NOT_FOUND", "Alert not found.", 404)
        with transaction.atomic():
            alert.referral_made = True
            alert.referral_note = request.data.get("note", "")
            alert.save(update_fields=["referral_made", "referral_note", "updated_at"])
            publish("ReferralRecorded", {"id": alert.id, "patient_id": alert.patient_id, "actor_id": request.user.id, "note": alert.referral_note})
        return Response(AlertSerializer(alert).data)


class AlertRuleListView(APIView):
    permission_classes = [has_role(Roles.SYSTEM_ADMIN, Roles.REGULATOR, Roles.PRESCRIBER, Roles.PHARMACIST)]

    def get(self, request):
        return Response(facade.rule_catalogue())


class AlertRuleUpdateView(APIView):
    permission_classes = [has_role(Roles.SYSTEM_ADMIN)]

    def patch(self, request, code):
        rule = RULES_BY_CODE.get(code.upper())
        if not rule:
            raise DomainError("RULE_NOT_FOUND", "Unknown rule code.", 404)
        params = request.data.get("params", {})
        unknown = set(params) - set(rule.defaults)
        if unknown:
            raise DomainError("UNKNOWN_PARAMS", f"Unknown parameters: {', '.join(sorted(unknown))}.")
        for k, v in params.items():
            if k == "severity":
                if v not in ("CRITICAL", "WARNING", "INFO"):
                    raise DomainError("INVALID_PARAM", "severity must be CRITICAL, WARNING or INFO.")
            elif not isinstance(v, (int, float)) or v < 0:
                raise DomainError("INVALID_PARAM", f"{k} must be a non-negative number.")
        with transaction.atomic():
            cfg, _ = RuleConfig.objects.get_or_create(code=rule.code)
            cfg.params = {**cfg.params, **params}
            if "enabled" in request.data:
                cfg.enabled = bool(request.data["enabled"])
            cfg.updated_by = request.user.id
            cfg.save()
            publish("AlertRuleChanged", {"id": rule.code, "actor_id": request.user.id, "params": cfg.params, "enabled": cfg.enabled})
        return Response(next(r for r in facade.rule_catalogue() if r["code"] == rule.code))
