"""Shipment lifecycle rules shared by the API and background jobs."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.enums import STATUS_TRANSITIONS, ShipmentStatus
from app.exceptions import ConflictError
from app.models import Shipment, ShipmentStatusHistory
from app.utils import utcnow


def allowed_transitions(current: str) -> list[ShipmentStatus]:
    return sorted(STATUS_TRANSITIONS[ShipmentStatus(current)], key=lambda s: list(ShipmentStatus).index(s))


def can_transition(current: str, target: str) -> bool:
    return ShipmentStatus(target) in STATUS_TRANSITIONS[ShipmentStatus(current)]


def apply_transition(
    db: Session,
    shipment: Shipment,
    target: ShipmentStatus,
    *,
    note: str | None = None,
    location: str | None = None,
    changed_by: str = "user",
    at: datetime | None = None,
) -> ShipmentStatusHistory:
    """Move a shipment to ``target`` and persist a history record.

    Raises ConflictError when the transition is not permitted by the lifecycle.
    """
    current = ShipmentStatus(shipment.status)
    target = ShipmentStatus(target)
    if target == current:
        raise ConflictError(f"Shipment is already '{current.value}'")
    if not can_transition(current, target):
        allowed = ", ".join(s.value for s in allowed_transitions(current)) or "none (terminal status)"
        raise ConflictError(
            f"Cannot change status from '{current.value}' to '{target.value}'. Allowed: {allowed}",
            field="status",
        )
    at = at or utcnow()
    shipment.status = target.value
    if location:
        shipment.current_location = location
    entry = ShipmentStatusHistory(
        shipment=shipment,
        from_status=current.value,
        to_status=target.value,
        location=location or shipment.current_location,
        note=note,
        changed_by=changed_by,
        changed_at=at,
    )
    db.add(entry)
    return entry


def record_initial_status(
    db: Session, shipment: Shipment, *, changed_by: str = "user", at: datetime | None = None
) -> ShipmentStatusHistory:
    entry = ShipmentStatusHistory(
        shipment=shipment,
        from_status=None,
        to_status=shipment.status,
        location=shipment.current_location,
        note="Shipment created",
        changed_by=changed_by,
        changed_at=at or utcnow(),
    )
    db.add(entry)
    return entry
