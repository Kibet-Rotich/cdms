"""Public interface of the Alerts module.

Prescription and Dispensing call:
    evaluate(...)  -> on preview: run rules, store an Evaluation, return findings
    confirm(...)   -> on commit: re-run rules (never trust the client) and check every finding is acknowledged
    record(...)    -> on commit: store the acknowledged alerts against the new prescription/dispense
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from core.events import publish
from core.exceptions import DomainError
from modules.history import facade as history
from modules.registry import facade as registry

from .models import Alert, Evaluation, RuleConfig
from .rules import RULES, run_rules

ACK_REASONS = {c for c, _ in Alert.AckReason.choices}


def load_configs():
    return {c.code: {"enabled": c.enabled, **c.params} for c in RuleConfig.objects.all()}


def rule_catalogue():
    configs = load_configs()
    return [
        {
            "code": r.code,
            "title": r.title,
            "description": r.description,
            "applies_to": list(r.applies_to),
            "defaults": r.defaults,
            "enabled": configs.get(r.code, {}).get("enabled", True),
            "params": {**r.defaults, **{k: v for k, v in configs.get(r.code, {}).items() if k != "enabled"}},
        }
        for r in RULES
    ]


def _build_context(action, patient_id, proposed, as_of):
    drug = registry.get_drug(proposed["drug_id"])
    if not drug:
        raise DomainError("DRUG_NOT_FOUND", "Drug not found in the catalogue.", 404)
    facility = registry.get_facility(proposed["facility_id"]) if proposed.get("facility_id") else None
    days = int(proposed["days_supply"])
    full = {
        **proposed,
        "drug_name": drug["name"],
        "class_code": drug["class_code"],
        "daily_mme": registry.daily_mme(drug, proposed["quantity"], days),
        "start_date": as_of,
        "end_date": as_of + timedelta(days=days),
        "facility_name": facility["name"] if facility else "",
    }
    return {
        "action": action,
        "as_of": as_of,
        "proposed": full,
        "history": history.get_supply_window(patient_id, as_of=as_of),
    }


def _run(action, patient_id, proposed, as_of):
    as_of = as_of or timezone.localdate()
    ctx = _build_context(action, patient_id, proposed, as_of)
    return ctx, [f.as_dict() for f in run_rules(ctx, load_configs())]


def evaluate(*, action, patient_id, proposed, actor, as_of=None):
    ctx, findings = _run(action, patient_id, proposed, as_of)
    ev = Evaluation.objects.create(
        action=action, patient_id=patient_id, actor_id=actor.get("id"), facility_id=actor.get("facility_id"),
        proposed=ctx["proposed"], findings=findings,
    )
    return {"evaluation_id": str(ev.id), "findings": findings, "proposed": ctx["proposed"]}


def confirm(*, action, patient_id, proposed, acknowledgements, evaluation_id=None, as_of=None):
    """Re-evaluate and require an acknowledgement (with reason) for every finding. Returns findings."""
    if evaluation_id:
        ev = Evaluation.objects.filter(id=evaluation_id).first()
        if not ev or str(ev.patient_id) != str(patient_id) or ev.action != action:
            raise DomainError("INVALID_EVALUATION", "evaluationId does not match this patient and action.")
    _, findings = _run(action, patient_id, proposed, as_of)
    acks = {a.get("rule_code"): a for a in (acknowledgements or [])}
    missing, invalid = [], []
    for f in findings:
        ack = acks.get(f["rule_code"])
        if not ack:
            missing.append(f)
        elif ack.get("reason") not in ACK_REASONS or (ack.get("reason") == "OTHER" and not (ack.get("note") or "").strip()):
            invalid.append(f["rule_code"])
    if missing or invalid:
        raise DomainError(
            "ALERTS_NOT_ACKNOWLEDGED",
            "Every alert must be acknowledged with a valid reason before continuing (a note is required for OTHER).",
            422,
            {"findings": findings, "missing": [f["rule_code"] for f in missing], "invalid": invalid},
        )
    return findings


def record(*, findings, acknowledgements, action, subject_type, subject_id, patient_id, facility_id,
           prescriber_key, actor, occurred_at, county_code, evaluation_id=None):
    acks = {a["rule_code"]: a for a in (acknowledgements or [])}
    created = []
    for f in findings:
        ack = acks[f["rule_code"]]
        alert = Alert.objects.create(
            evaluation_id=evaluation_id, action=action, subject_type=subject_type, subject_id=subject_id,
            patient_id=patient_id, facility_id=facility_id, prescriber_key=prescriber_key or "",
            rule_code=f["rule_code"], severity=f["severity"], title=f["title"], message=f["message"],
            details=f["details"], acknowledged_by=actor.get("id"), acknowledged_by_name=actor.get("full_name", ""),
            ack_reason=ack["reason"], ack_note=ack.get("note", ""),
            referral_made=bool(ack.get("referral")), referral_note=ack.get("referral_note", ""),
            occurred_at=occurred_at, county_code=county_code,
        )
        publish("AlertRaised", {
            "id": alert.id, "patient_id": patient_id, "rule_code": alert.rule_code, "severity": alert.severity,
            "subject_type": subject_type, "subject_id": subject_id, "actor_id": actor.get("id"), "ack_reason": alert.ack_reason,
        })
        created.append(alert)
    return created


# ---- Queries for other modules (Oversight) ------------------------------------------------------

def _alerts(county_code, date_from, date_to):
    return Alert.objects.filter(county_code=county_code, occurred_at__date__gte=date_from, occurred_at__date__lte=date_to)


def alert_totals(county_code, date_from, date_to):
    qs = _alerts(county_code, date_from, date_to)
    return {
        "alerts": qs.count(),
        "critical": qs.filter(severity="CRITICAL").count(),
        "warning": qs.filter(severity="WARNING").count(),
        "referrals": qs.filter(referral_made=True).count(),
        "by_rule": list(qs.values("rule_code", "title").annotate(n=Count("id"), critical=Count("id", filter=Q(severity="CRITICAL"))).order_by("-n")),
        "by_reason": list(qs.values("ack_reason").annotate(n=Count("id")).order_by("-n")),
    }


def counts_by_facility(county_code, date_from, date_to):
    rows = _alerts(county_code, date_from, date_to).filter(action="DISPENSE").values("facility_id").annotate(
        n=Count("id"), critical=Count("id", filter=Q(severity="CRITICAL")))
    return {str(r["facility_id"]): r for r in rows}


def counts_by_prescriber(county_code, date_from, date_to):
    rows = _alerts(county_code, date_from, date_to).exclude(prescriber_key="").values("prescriber_key").annotate(
        n=Count("id"), critical=Count("id", filter=Q(severity="CRITICAL")))
    return {r["prescriber_key"]: r for r in rows}


def patients_with_critical_alerts(county_code, date_from, date_to, min_critical=2):
    rows = (
        _alerts(county_code, date_from, date_to)
        .values("patient_id")
        .annotate(critical=Count("id", filter=Q(severity="CRITICAL")), total=Count("id"))
        .filter(critical__gte=min_critical)
        .order_by("-critical", "-total")
    )
    out = []
    for r in rows:
        rules = list(
            _alerts(county_code, date_from, date_to).filter(patient_id=r["patient_id"]).order_by("rule_code")
            .values_list("rule_code", flat=True).distinct()
        )
        last = _alerts(county_code, date_from, date_to).filter(patient_id=r["patient_id"]).order_by("-occurred_at").first()
        out.append({"patient_id": str(r["patient_id"]), "critical": r["critical"], "total": r["total"],
                    "rules": rules, "last_alert_at": last.occurred_at if last else None})
    return out
