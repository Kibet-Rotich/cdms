"""In-process domain event bus backed by a transactional outbox.

Usage:
    publish("DispenseRecorded", {...})          # inside the same DB transaction as the change
    subscribe("DispenseRecorded", handler)      # in a module's AppConfig.ready()

Handlers always receive the payload as stored in the outbox (JSON: UUIDs/dates are strings),
which is exactly what they would receive from a message broker after a microservice split.
"""
import logging
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

_subscribers = defaultdict(list)


def subscribe(event_name, handler):
    if handler not in _subscribers[event_name]:
        _subscribers[event_name].append(handler)


def publish(event_name, payload):
    from core.models import OutboxEvent

    event = OutboxEvent.objects.create(name=event_name, payload=payload)
    transaction.on_commit(lambda: dispatch(event.id))
    return event.id


def dispatch(event_id):
    from core.models import OutboxEvent

    event = OutboxEvent.objects.filter(id=event_id, processed_at__isnull=True).first()
    if event is None:
        return
    errors = []
    for handler in _subscribers.get(event.name, []):
        try:
            with transaction.atomic():
                handler(event.payload)
        except Exception as exc:  # keep other subscribers running; retry via process_outbox
            logger.exception("Event handler %s failed for %s", handler, event.name)
            errors.append(f"{handler.__module__}.{handler.__name__}: {exc}")
    if errors:
        event.error = "\n".join(errors)
        event.save(update_fields=["error"])
    else:
        event.processed_at = timezone.now()
        event.error = ""
        event.save(update_fields=["processed_at", "error"])


def process_pending():
    """Re-deliver events that were not processed (e.g. after a crash)."""
    from core.models import OutboxEvent

    ids = list(OutboxEvent.objects.filter(processed_at__isnull=True).values_list("id", flat=True))
    for event_id in ids:
        dispatch(event_id)
    return len(ids)
