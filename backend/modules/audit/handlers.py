"""Audit subscribes to every domain event so all writes are logged without other modules knowing."""
from core.events import subscribe

from .facade import record

AUDITED_EVENTS = [
    "UserRegistered", "UserApproved", "UserSuspended",
    "PatientRegistered", "PatientLinkedFromRegistry",
    "PrescriptionCreated", "PrescriptionCancelled", "PrescriptionExpired",
    "DispenseRecorded", "DispenseVoided",
    "AlertRaised", "ReferralRecorded",
    "StockReceived", "AlertRuleChanged",
]


def _make_handler(name):
    def handler(payload):
        actor_id = payload.get("actor_id") or payload.get("by")
        record(
            action=f"EVENT:{name}",
            resource_type=name,
            resource_id=payload.get("id") or payload.get("dispense_id") or payload.get("prescription_id") or payload.get("user_id") or "",
            actor={"id": actor_id} if actor_id else None,
            patient_id=payload.get("patient_id"),
            details=payload,
        )

    handler.__name__ = f"audit_{name}"
    return handler


def register():
    for name in AUDITED_EVENTS:
        subscribe(name, _make_handler(name))
