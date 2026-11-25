"""Regulator dashboard. Read-only: composes data from other modules' facades (owns no tables in the MVP)."""
import csv
import statistics
from datetime import date, timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import DomainError
from core.permissions import Roles, actor_of, has_role
from modules.alerts import facade as alerts
from modules.audit import facade as audit
from modules.history import facade as history
from modules.patients import facade as patients
from modules.registry import facade as registry
from modules.supply import facade as supply

PERMS = [IsAuthenticated, has_role(Roles.REGULATOR, Roles.SYSTEM_ADMIN)]
OUTLIER_RATIO = 3.0


def _range(request, default_days=90):
    p = request.query_params
    try:
        date_to = date.fromisoformat(p["to"]) if p.get("to") else timezone.localdate()
        date_from = date.fromisoformat(p["from"]) if p.get("from") else date_to - timedelta(days=default_days)
    except ValueError:
        raise DomainError("INVALID_DATE", "Dates must be YYYY-MM-DD.")
    return date_from, date_to


def _median(values):
    values = [v for v in values if v]
    return statistics.median(values) if values else 0


class SummaryView(APIView):
    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request)
        county = request.user.county_code
        return Response({
            "from": f, "to": t, "county_code": county,
            **history.dispense_totals(county, f, t),
            "alerts": alerts.alert_totals(county, f, t),
        })


class TrendsView(APIView):
    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request, default_days=182)
        return Response({"from": f, "to": t, "weeks": history.weekly_trend(request.user.county_code, f, t)})


class PrescriberOutliersView(APIView):
    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request)
        county = request.user.county_code
        rows = history.prescriber_stats(county, f, t)
        alert_counts = alerts.counts_by_prescriber(county, f, t)
        median_opioid = _median([r["opioid_prescriptions"] for r in rows])
        for r in rows:
            a = alert_counts.get(r["prescriber_key"], {})
            r["alerts"] = a.get("n", 0)
            r["critical_alerts"] = a.get("critical", 0)
            r["alert_rate"] = round(r["alerts"] / r["prescriptions"], 2) if r["prescriptions"] else 0
            r["ratio_to_median"] = round(r["opioid_prescriptions"] / median_opioid, 1) if median_opioid else 0
            r["outlier"] = r["ratio_to_median"] >= OUTLIER_RATIO
        rows.sort(key=lambda r: (r["ratio_to_median"], r["alerts"]), reverse=True)
        return Response({"from": f, "to": t, "median_opioid_prescriptions": median_opioid, "outlier_ratio": OUTLIER_RATIO, "items": rows})


class PharmacyOutliersView(APIView):
    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request)
        county = request.user.county_code
        rows = history.pharmacy_stats(county, f, t)
        alert_counts = alerts.counts_by_facility(county, f, t)
        median_dispenses = _median([r["dispenses"] for r in rows])
        for r in rows:
            a = alert_counts.get(r["facility_id"], {})
            r["alerts"] = a.get("n", 0)
            r["critical_alerts"] = a.get("critical", 0)
            r["alert_rate"] = round(r["alerts"] / r["dispenses"], 2) if r["dispenses"] else 0
            r["ratio_to_median"] = round(r["dispenses"] / median_dispenses, 1) if median_dispenses else 0
            r["outlier"] = r["ratio_to_median"] >= OUTLIER_RATIO
        rows.sort(key=lambda r: (r["critical_alerts"], r["alerts"]), reverse=True)
        return Response({"from": f, "to": t, "median_dispenses": median_dispenses, "items": rows})


class HotspotsView(APIView):
    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request)
        county = request.user.county_code
        facilities = registry.get_facilities_map(county)
        by_sub = {r["sub_county"]: {**r, "alerts": 0, "critical_alerts": 0} for r in history.sub_county_stats(county, f, t)}
        for fid, a in alerts.counts_by_facility(county, f, t).items():
            sub = facilities.get(fid, {}).get("sub_county")
            if sub:
                row = by_sub.setdefault(sub, {"sub_county": sub, "dispenses": 0, "patients": 0, "quantity": 0, "alerts": 0, "critical_alerts": 0})
                row["alerts"] += a["n"]
                row["critical_alerts"] += a["critical"]
        items = sorted(by_sub.values(), key=lambda r: r["critical_alerts"], reverse=True)
        for r in items:
            r["alerts_per_100_dispenses"] = round(100 * r["alerts"] / r["dispenses"], 1) if r["dispenses"] else 0
        return Response({"from": f, "to": t, "items": items})


class FlaggedPatientsView(APIView):
    """Patients with repeated critical alerts. Identities are pseudonymised until explicitly revealed."""

    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request)
        rows = alerts.patients_with_critical_alerts(request.user.county_code, f, t, int(request.query_params.get("minCritical", 2)))
        return Response({"from": f, "to": t, "items": [
            {"ref": patients.pseudonym(r["patient_id"]), "critical": r["critical"], "total": r["total"],
             "rules": r["rules"], "last_alert_at": r["last_alert_at"]}
            for r in rows
        ]})


class RevealFlaggedPatientView(APIView):
    permission_classes = [IsAuthenticated, has_role(Roles.REGULATOR)]

    def post(self, request, ref):
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            raise DomainError("REASON_REQUIRED", "Give a reason (investigation reference) to reveal a patient's identity.")
        today = timezone.localdate()
        rows = alerts.patients_with_critical_alerts(request.user.county_code, today - timedelta(days=365), today, 1)
        match = next((r for r in rows if patients.pseudonym(r["patient_id"]) == ref), None)
        if not match:
            raise DomainError("NOT_FOUND", "No flagged patient with this reference.", 404)
        actor = actor_of(request)
        audit.record(action="REVEAL_IDENTITY", resource_type="Patient", resource_id=match["patient_id"], actor=actor,
                     patient_id=match["patient_id"], purpose="OVERSIGHT", details={"ref": ref, "reason": reason})
        return Response({"ref": ref, "patient": patients.get_patient(match["patient_id"])})


def _reconciliation(county, f, t):
    received = supply.received_quantity_by_facility_drug(county, f, t)
    items = []
    for r in history.dispensed_quantity_by_facility_drug(county, f, t):
        rec = received.get((r["facility_id"], r["drug_id"]), 0.0)
        gap = round(r["quantity"] - rec, 1)
        items.append({
            "facility_id": r["facility_id"], "facility_name": r["facility_name"], "drug_name": r["drug_name"],
            "received": rec, "dispensed": r["quantity"], "gap": gap,
            "flag": gap > 0,  # dispensed more than received => stock from an unrecorded source
        })
    items.sort(key=lambda x: x["gap"], reverse=True)
    return items


class SupplyReconciliationView(APIView):
    permission_classes = PERMS

    def get(self, request):
        f, t = _range(request, default_days=182)
        return Response({"from": f, "to": t, "items": _reconciliation(request.user.county_code, f, t)})


class ExportView(APIView):
    permission_classes = PERMS

    def get(self, request):
        report = request.query_params.get("type", "pharmacies")
        f, t = _range(request)
        county = request.user.county_code
        if report == "pharmacies":
            rows = history.pharmacy_stats(county, f, t)
        elif report == "prescribers":
            rows = history.prescriber_stats(county, f, t)
        elif report == "supply":
            rows = _reconciliation(county, f, t)
        else:
            raise DomainError("UNKNOWN_REPORT", "type must be pharmacies, prescribers or supply.")
        audit.record(action="EXPORT", resource_type=f"Report:{report}", actor=actor_of(request), purpose="OVERSIGHT",
                     details={"from": f.isoformat(), "to": t.isoformat(), "rows": len(rows)})
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{report}_{f}_{t}.csv"'
        if rows:
            writer = csv.DictWriter(response, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return response
