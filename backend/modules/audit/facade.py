"""Public interface of the Audit module. Writing happens only through `record` and event subscriptions."""
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent


def record(*, action, resource_type, resource_id="", actor=None, patient_id=None, purpose=None, details=None):
    """Append an audit event. `actor` is the dict produced by core.permissions.actor_of (or None for system)."""
    actor = actor or {}
    with transaction.atomic():
        last = AuditEvent.objects.select_for_update().order_by("-seq").first()
        event = AuditEvent(
            occurred_at=timezone.now(),
            actor_id=actor.get("id"),
            actor_name=actor.get("full_name", "") or "",
            actor_role=actor.get("role", "") or "",
            facility_id=actor.get("facility_id"),
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id or ""),
            patient_id=patient_id,
            purpose=purpose or actor.get("purpose") or "",
            ip_address=actor.get("ip") or "",
            details=details or {},
            prev_hash=last.hash if last else "",
        )
        event.hash = event.compute_hash()
        event.save()
    return event.seq


def verify_chain():
    """Recompute every hash; return (ok, first_broken_seq)."""
    prev = ""
    for ev in AuditEvent.objects.order_by("seq").iterator():
        if ev.prev_hash != prev or ev.compute_hash() != ev.hash:
            return False, ev.seq
        prev = ev.hash
    return True, None
