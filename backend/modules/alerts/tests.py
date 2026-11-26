"""Unit tests for alert rules. Rules are pure functions of a context, so no database is needed."""
from datetime import date, timedelta

from django.test import SimpleTestCase

from .rules import run_rules

TODAY = date(2026, 11, 6)


def event(kind="DISPENSED", cls="OPIOID", start_ago=5, days=10, prescriber="A1", facility="F1", mme=30.0, source="s1"):
    start = TODAY - timedelta(days=start_ago)
    return {
        "kind": kind, "source_id": source, "prescription_id": None, "drug_name": f"{cls} drug", "class_code": cls,
        "quantity": 30, "days_supply": days, "start_date": start, "end_date": start + timedelta(days=days),
        "daily_mme": mme, "prescriber_key": prescriber, "prescriber_name": f"Dr {prescriber}",
        "facility_id": facility, "facility_name": f"Facility {facility}",
    }


def proposal(cls="OPIOID", days=10, prescriber="A1", facility="F1", mme=30.0, **extra):
    return {
        "drug_id": "d", "drug_name": f"{cls} drug", "class_code": cls, "quantity": 30, "days_supply": days,
        "daily_mme": mme, "start_date": TODAY, "end_date": TODAY + timedelta(days=days), "prescriber_key": prescriber,
        "prescriber_name": f"Dr {prescriber}", "facility_id": facility, "facility_name": f"Facility {facility}",
        "prescription_id": None, "is_paper": False, "paper_licence_verified": True, **extra,
    }


def codes(action, history, prop, configs=None):
    ctx = {"action": action, "as_of": TODAY, "proposed": prop, "history": history}
    return {f.rule_code: f.severity for f in run_rules(ctx, configs or {})}


class RuleTests(SimpleTestCase):
    def test_clean_history_has_no_alerts(self):
        self.assertEqual(codes("DISPENSE", [], proposal()), {})

    def test_early_refill(self):
        # 10-day supply dispensed 2 days ago -> 80% remains
        self.assertIn("EARLY_REFILL", codes("DISPENSE", [event(start_ago=2)], proposal()))
        # dispensed 9 days ago -> 10% remains, under the 25% threshold
        self.assertNotIn("EARLY_REFILL", codes("DISPENSE", [event(start_ago=9)], proposal()))

    def test_duplicate_therapy_needs_a_different_prescriber(self):
        self.assertIn("DUPLICATE_THERAPY", codes("PRESCRIBE", [event(kind="PRESCRIBED", prescriber="A2")], proposal()))
        self.assertNotIn("DUPLICATE_THERAPY", codes("PRESCRIBE", [event(kind="PRESCRIBED", prescriber="A1")], proposal()))

    def test_multiple_prescribers_severity(self):
        hist = [event(prescriber=f"A{i}", start_ago=20 + i, source=f"s{i}") for i in range(2, 4)]  # 2 others + proposed = 3
        self.assertEqual(codes("PRESCRIBE", hist, proposal())["MULTIPLE_PRESCRIBERS"], "WARNING")
        hist.append(event(prescriber="A9", start_ago=25, source="s9"))  # 4 total
        self.assertEqual(codes("PRESCRIBE", hist, proposal())["MULTIPLE_PRESCRIBERS"], "CRITICAL")

    def test_multiple_pharmacies_only_on_dispense(self):
        hist = [event(facility=f"F{i}", start_ago=15 + i, source=f"s{i}") for i in range(2, 5)]
        self.assertEqual(codes("DISPENSE", hist, proposal())["MULTIPLE_PHARMACIES"], "CRITICAL")
        self.assertNotIn("MULTIPLE_PHARMACIES", codes("PRESCRIBE", hist, proposal()))

    def test_opioid_benzo_overlap(self):
        hist = [event(cls="BENZODIAZEPINE", start_ago=3, days=14, mme=0)]
        self.assertEqual(codes("DISPENSE", hist, proposal(cls="OPIOID"))["OPIOID_BENZO_OVERLAP"], "CRITICAL")

    def test_high_daily_mme_counts_active_supply(self):
        self.assertEqual(codes("DISPENSE", [], proposal(mme=95))["HIGH_DAILY_MME"], "CRITICAL")
        self.assertEqual(codes("DISPENSE", [event(start_ago=3, mme=30)], proposal(mme=30))["HIGH_DAILY_MME"], "WARNING")

    def test_high_daily_mme_ignores_supply_ending_within_grace(self):
        # previous 10-day supply ends tomorrow (on-time refill) -> not counted
        self.assertNotIn("HIGH_DAILY_MME", codes("DISPENSE", [event(start_ago=9, mme=30)], proposal(mme=30)))

    def test_unknown_paper_licence(self):
        prop = proposal(is_paper=True, paper_licence_verified=False)
        self.assertIn("UNKNOWN_PRESCRIBER_LICENCE", codes("DISPENSE", [], prop))

    def test_rules_can_be_disabled_and_thresholds_changed(self):
        hist = [event(start_ago=2)]
        self.assertNotIn("EARLY_REFILL", codes("DISPENSE", hist, proposal(), {"EARLY_REFILL": {"enabled": False}}))
        self.assertNotIn("EARLY_REFILL", codes("DISPENSE", hist, proposal(), {"EARLY_REFILL": {"remaining_fraction": 0.9}}))
