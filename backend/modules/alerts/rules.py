"""Alert rules. Each rule is a small, pure class: no database access, easy to unit test.

To add a rule: write a class with `code`, `title`, `applies_to`, `defaults` and `evaluate`, then add it to RULES.

EvaluationContext (dict):
    action:    "PRESCRIBE" | "DISPENSE"
    as_of:     date of the action
    proposed:  {drug_id, drug_name, class_code, quantity, days_supply, daily_mme, start_date, end_date,
                prescriber_key, prescriber_name, facility_id, facility_name, prescription_id,
                is_paper, paper_licence_verified}
    history:   list of medication events (see history.facade.event_dto), status ACTIVE only
"""
from dataclasses import dataclass, field
from datetime import timedelta

CRITICAL, WARNING, INFO = "CRITICAL", "WARNING", "INFO"
SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}


@dataclass
class Finding:
    rule_code: str
    severity: str
    title: str
    message: str
    details: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "rule_code": self.rule_code,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "details": self.details,
        }


def _fmt(d):
    return d.strftime("%d %b %Y")


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _same_source(event, proposed):
    """True when a history event is the prescription being dispensed (don't compare it with itself)."""
    return bool(proposed.get("prescription_id")) and event["source_id"] == proposed["prescription_id"]


class Rule:
    code = ""
    title = ""
    description = ""
    applies_to = ("PRESCRIBE", "DISPENSE")
    defaults = {}

    def evaluate(self, ctx, cfg):
        raise NotImplementedError


class EarlyRefill(Rule):
    code = "EARLY_REFILL"
    title = "Early refill"
    description = "New supply of the same drug class while a large part of the previous supply should remain."
    applies_to = ("DISPENSE",)
    defaults = {"severity": WARNING, "remaining_fraction": 0.25}

    def evaluate(self, ctx, cfg):
        p, as_of = ctx["proposed"], ctx["as_of"]
        worst = None
        for e in ctx["history"]:
            if e["kind"] != "DISPENSED" or e["class_code"] != p["class_code"] or e["end_date"] <= as_of:
                continue
            remaining_days = (e["end_date"] - as_of).days
            fraction = remaining_days / max(e["days_supply"], 1)
            if fraction > cfg["remaining_fraction"] and (worst is None or fraction > worst[1]):
                worst = (e, fraction, remaining_days)
        if not worst:
            return []
        e, fraction, remaining_days = worst
        return [Finding(
            self.code, cfg["severity"], self.title,
            f"{e['drug_name']} dispensed at {e['facility_name']} on {_fmt(e['start_date'])} should last until "
            f"{_fmt(e['end_date'])}: about {remaining_days} days ({round(fraction * 100)}%) of that supply should remain.",
            {"previous_dispense_id": e["source_id"], "remaining_days": remaining_days,
             "remaining_fraction": round(fraction, 2), "threshold": cfg["remaining_fraction"]},
        )]


class DuplicateTherapy(Rule):
    code = "DUPLICATE_THERAPY"
    title = "Duplicate therapy"
    description = "Overlapping supply of the same drug class from a different prescriber."
    defaults = {"severity": WARNING}

    def evaluate(self, ctx, cfg):
        p = ctx["proposed"]
        others = {}
        for e in ctx["history"]:
            if e["class_code"] != p["class_code"] or _same_source(e, p):
                continue
            if not e["prescriber_key"] or e["prescriber_key"] == p["prescriber_key"]:
                continue
            if _overlaps(e["start_date"], e["end_date"], p["start_date"], p["end_date"]):
                others.setdefault(e["prescriber_key"], e)
        if not others:
            return []
        names = ", ".join(f"{e['prescriber_name']} ({e['drug_name']}, {_fmt(e['start_date'])})" for e in others.values())
        return [Finding(
            self.code, cfg["severity"], self.title,
            f"Patient already has overlapping {p['class_code'].lower()} supply from another prescriber: {names}.",
            {"other_prescribers": list(others.keys()), "class_code": p["class_code"]},
        )]


class _CountRule(Rule):
    """Counts distinct values (prescribers / pharmacies) over a window, including the proposed action."""

    key = ""
    noun = ""
    kinds = ("PRESCRIBED", "DISPENSED")

    def evaluate(self, ctx, cfg):
        p, as_of = ctx["proposed"], ctx["as_of"]
        since = as_of - timedelta(days=cfg["window_days"])
        seen = {}
        for e in ctx["history"]:
            if e["kind"] in self.kinds and e["start_date"] >= since and e[self.key]:
                seen.setdefault(e[self.key], e)
        if p.get(self.key):
            seen.setdefault(p[self.key], None)
        n = len(seen)
        if n >= cfg["critical_at"]:
            severity = "CRITICAL"
        elif n >= cfg["warning_at"]:
            severity = "WARNING"
        else:
            return []
        return [Finding(
            self.code, severity, self.title,
            f"{n} different {self.noun} for monitored medicines in the last {cfg['window_days']} days "
            f"(including this one). Warning at {cfg['warning_at']}, critical at {cfg['critical_at']}.",
            {"count": n, "window_days": cfg["window_days"], "keys": list(seen.keys())},
        )]


class MultiplePrescribers(_CountRule):
    code = "MULTIPLE_PRESCRIBERS"
    title = "Multiple prescribers"
    description = "Patient obtained monitored medicines from several prescribers in a short period."
    key = "prescriber_key"
    noun = "prescribers"
    defaults = {"window_days": 30, "warning_at": 3, "critical_at": 4}


class MultiplePharmacies(_CountRule):
    code = "MULTIPLE_PHARMACIES"
    title = "Multiple pharmacies"
    description = "Patient collected monitored medicines from several pharmacies in a short period."
    applies_to = ("DISPENSE",)
    key = "facility_id"
    noun = "pharmacies"
    kinds = ("DISPENSED",)
    defaults = {"window_days": 30, "warning_at": 3, "critical_at": 4}


class OpioidBenzoOverlap(Rule):
    code = "OPIOID_BENZO_OVERLAP"
    title = "Opioid + benzodiazepine"
    description = "Overlapping opioid and benzodiazepine supply (high overdose risk)."
    defaults = {"severity": CRITICAL}
    PAIR = {"OPIOID": "BENZODIAZEPINE", "BENZODIAZEPINE": "OPIOID"}

    def evaluate(self, ctx, cfg):
        p = ctx["proposed"]
        other_class = self.PAIR.get(p["class_code"])
        if not other_class:
            return []
        hits = [
            e for e in ctx["history"]
            if e["kind"] == "DISPENSED" and e["class_code"] == other_class
            and _overlaps(e["start_date"], e["end_date"], p["start_date"], p["end_date"])
        ]
        if not hits:
            return []
        e = max(hits, key=lambda x: x["end_date"])
        return [Finding(
            self.code, cfg["severity"], self.title,
            f"Patient has active {other_class.lower()} supply ({e['drug_name']}, until {_fmt(e['end_date'])}). "
            f"Combining opioids and benzodiazepines greatly increases overdose risk.",
            {"overlapping_dispense_ids": [h["source_id"] for h in hits]},
        )]


class HighDailyMme(Rule):
    code = "HIGH_DAILY_MME"
    title = "High daily opioid dose"
    description = "Total daily morphine milligram equivalents (MME) above the threshold."
    defaults = {"warning_at": 50, "critical_at": 90, "overlap_grace_days": 2}

    def evaluate(self, ctx, cfg):
        p = ctx["proposed"]
        if p["class_code"] != "OPIOID":
            return []
        # Supplies ending within the grace period (e.g. a refill collected a day early) are not counted.
        grace = timedelta(days=cfg["overlap_grace_days"])
        active = [
            e for e in ctx["history"]
            if e["kind"] == "DISPENSED" and e["class_code"] == "OPIOID" and not _same_source(e, p)
            and _overlaps(e["start_date"], e["end_date"] - grace, p["start_date"], p["end_date"])
        ]
        total = round(p["daily_mme"] + sum(e["daily_mme"] for e in active), 1)
        if total >= cfg["critical_at"]:
            severity = "CRITICAL"
        elif total >= cfg["warning_at"]:
            severity = "WARNING"
        else:
            return []
        return [Finding(
            self.code, severity, self.title,
            f"Total opioid dose would be about {total} MME/day ({p['daily_mme']} from this supply"
            f"{f', {round(total - p['daily_mme'], 1)} from active supplies' if active else ''}). "
            f"Warning at {cfg['warning_at']}, critical at {cfg['critical_at']}.",
            {"total_daily_mme": total, "proposed_daily_mme": p["daily_mme"]},
        )]


class UnknownPrescriberLicence(Rule):
    code = "UNKNOWN_PRESCRIBER_LICENCE"
    title = "Prescriber licence not found"
    description = "The licence number on a paper prescription is not in the practitioner registry."
    applies_to = ("DISPENSE",)
    defaults = {"severity": WARNING}

    def evaluate(self, ctx, cfg):
        p = ctx["proposed"]
        if not p.get("is_paper") or p.get("paper_licence_verified"):
            return []
        return [Finding(
            self.code, cfg["severity"], self.title,
            f"Licence '{p.get('prescriber_key') or '(blank)'}' on this paper prescription was not found in the "
            f"practitioner registry. Verify the prescription with the prescriber before dispensing.",
            {"licence": p.get("prescriber_key")},
        )]


RULES = [
    EarlyRefill(), DuplicateTherapy(), MultiplePrescribers(), MultiplePharmacies(),
    OpioidBenzoOverlap(), HighDailyMme(), UnknownPrescriberLicence(),
]
RULES_BY_CODE = {r.code: r for r in RULES}


def run_rules(ctx, configs):
    """configs: {rule_code: {"enabled": bool, **params}}. Returns findings sorted by severity."""
    findings = []
    for rule in RULES:
        cfg = {**rule.defaults, **configs.get(rule.code, {})}
        if not cfg.get("enabled", True) or ctx["action"] not in rule.applies_to:
            continue
        findings.extend(rule.evaluate(ctx, cfg))
    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))
