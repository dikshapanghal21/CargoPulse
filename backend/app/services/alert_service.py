"""Alert management and overdue-shipment detection."""

from datetime import datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, joinedload

from app.enums import (
    ACTIVE_STATUSES,
    SEVERITY_RANK,
    TERMINAL_STATUSES,
    AlertSeverity,
    AlertStatus,
    AlertType,
    ShipmentPriority,
    ShipmentStatus,
    values,
)
from app.exceptions import ConflictError, NotFoundError
from app.models import Alert, Shipment
from app.schemas.alert import AlertCounts, AlertRead, ScanResult
from app.schemas.common import Page
from app.services.common import count_rows, like_pattern
from app.services.lifecycle import apply_transition
from app.utils import ensure_aware, page_count, utcnow

SYSTEM_ACTOR = "system:overdue-monitor"

_SEVERITY_ORDER = list(AlertSeverity)


def severity_rank_expr():
    return case(
        {s.value: rank for s, rank in SEVERITY_RANK.items()}, value=Alert.severity, else_=0
    )


def severity_for(hours_overdue: float, priority: str) -> AlertSeverity:
    if hours_overdue < 6:
        level = AlertSeverity.LOW
    elif hours_overdue < 24:
        level = AlertSeverity.MEDIUM
    elif hours_overdue < 72:
        level = AlertSeverity.HIGH
    else:
        level = AlertSeverity.CRITICAL
    bump = {ShipmentPriority.CRITICAL.value: 2, ShipmentPriority.EXPRESS.value: 1}.get(priority, 0)
    index = min(_SEVERITY_ORDER.index(level) + bump, len(_SEVERITY_ORDER) - 1)
    return _SEVERITY_ORDER[index]


def overdue_dedupe_key(shipment: Shipment) -> str:
    """One overdue alert per shipment per committed ETA."""
    eta = ensure_aware(shipment.eta)
    return f"{AlertType.OVERDUE.value}:{shipment.id}:{int(eta.timestamp())}"


def _overdue_message(shipment: Shipment) -> str:
    eta = ensure_aware(shipment.eta)
    return (
        f"Shipment {shipment.tracking_id} for {shipment.customer_name} missed its ETA of "
        f"{eta:%Y-%m-%d %H:%M} UTC on {shipment.route.origin_city} → "
        f"{shipment.route.destination_city} ({shipment.carrier.name})."
    )


def resolve_alert(
    alert: Alert, *, note: str | None, resolved_by: str, at: datetime | None = None
) -> None:
    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_at = at or utcnow()
    alert.resolution_note = note
    alert.resolved_by = resolved_by


def _stale_reason(alert: Alert, shipment: Shipment, cutoff: datetime) -> str | None:
    if shipment.status in values(TERMINAL_STATUSES):
        return f"Auto-resolved: shipment {shipment.status.replace('_', ' ')}"
    if alert.alert_type == AlertType.OVERDUE.value:
        if ensure_aware(shipment.eta) >= cutoff:
            return f"Auto-resolved: ETA revised to {ensure_aware(shipment.eta):%Y-%m-%d %H:%M} UTC"
        if alert.dedupe_key != overdue_dedupe_key(shipment):
            return "Superseded: ETA revised but still overdue"
    return None


def resolve_stale_alerts_for_shipment(
    db: Session, shipment: Shipment, *, now: datetime | None = None, grace_minutes: int = 0
) -> int:
    """Resolve active alerts on one shipment whose triggering condition no longer holds."""
    now = now or utcnow()
    cutoff = now - timedelta(minutes=grace_minutes)
    active = db.scalars(
        select(Alert).where(
            Alert.shipment_id == shipment.id, Alert.status == AlertStatus.ACTIVE.value
        )
    ).all()
    resolved = 0
    for alert in active:
        reason = _stale_reason(alert, shipment, cutoff)
        if reason:
            resolve_alert(alert, note=reason, resolved_by=SYSTEM_ACTOR, at=now)
            resolved += 1
    if resolved:
        db.flush()
    return resolved


def detect_overdue_shipments(
    db: Session, *, now: datetime | None = None, grace_minutes: int = 0
) -> ScanResult:
    """Flag overdue shipments, raise de-duplicated alerts and resolve stale ones.

    Idempotent: running it repeatedly with no data changes creates no new alerts.
    De-duplication is enforced in the database by a unique ``dedupe_key`` and a
    partial unique index (one active alert per shipment and type), and inserts use
    ``ON CONFLICT DO NOTHING`` so concurrent runs cannot double-insert.
    """
    now = now or utcnow()
    cutoff = now - timedelta(minutes=grace_minutes)
    result = ScanResult(scanned_at=now)

    # 1) Resolve active alerts whose condition has cleared (delivered, cancelled, ETA moved).
    active_alerts = db.scalars(
        select(Alert)
        .where(Alert.status == AlertStatus.ACTIVE.value, Alert.alert_type == AlertType.OVERDUE.value)
        .options(joinedload(Alert.shipment))
        .with_for_update(of=Alert, skip_locked=True)
    ).all()
    for alert in active_alerts:
        reason = _stale_reason(alert, alert.shipment, cutoff)
        if reason:
            resolve_alert(alert, note=reason, resolved_by=SYSTEM_ACTOR, at=now)
            result.alerts_resolved += 1
    db.flush()

    # 2) Detect overdue shipments.
    overdue = db.scalars(
        select(Shipment)
        .where(Shipment.status.in_(values(ACTIVE_STATUSES)), Shipment.eta < cutoff)
        .options(joinedload(Shipment.carrier), joinedload(Shipment.route))
        .order_by(Shipment.eta)
        .with_for_update(of=Shipment, skip_locked=True)
    ).all()
    result.overdue_found = len(overdue)

    active_by_shipment = {
        a.shipment_id: a
        for a in db.scalars(
            select(Alert).where(
                Alert.status == AlertStatus.ACTIVE.value,
                Alert.alert_type == AlertType.OVERDUE.value,
                Alert.shipment_id.in_([s.id for s in overdue] or [0]),
            )
        ).all()
    }

    for shipment in overdue:
        hours = (now - ensure_aware(shipment.eta)).total_seconds() / 3600
        severity = severity_for(hours, shipment.priority)
        existing = active_by_shipment.get(shipment.id)

        if existing is not None:
            if SEVERITY_RANK[severity] > SEVERITY_RANK[AlertSeverity(existing.severity)]:
                existing.severity = severity.value
                result.alerts_escalated += 1
            else:
                result.duplicates_skipped += 1
        else:
            stmt = (
                pg_insert(Alert)
                .values(
                    shipment_id=shipment.id,
                    alert_type=AlertType.OVERDUE.value,
                    severity=severity.value,
                    status=AlertStatus.ACTIVE.value,
                    message=_overdue_message(shipment),
                    dedupe_key=overdue_dedupe_key(shipment),
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
                .returning(Alert.id)
            )
            if db.execute(stmt).scalar_one_or_none() is not None:
                result.alerts_created += 1
            else:
                result.duplicates_skipped += 1

        if shipment.status != ShipmentStatus.DELAYED.value:
            apply_transition(
                db,
                shipment,
                ShipmentStatus.DELAYED,
                note=f"ETA passed ({ensure_aware(shipment.eta):%Y-%m-%d %H:%M} UTC); "
                "automatically flagged as delayed",
                changed_by=SYSTEM_ACTOR,
                at=now,
            )
            result.shipments_marked_delayed += 1

    db.commit()
    return result


# --------------------------------------------------------------------------- queries


def _alert_query():
    return (
        select(Alert)
        .join(Alert.shipment)
        .options(joinedload(Alert.shipment))
    )


def list_alerts(
    db: Session,
    *,
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    shipment_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[AlertRead]:
    stmt = _alert_query()
    if status is not None:
        stmt = stmt.where(Alert.status == status.value)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity.value)
    if shipment_id is not None:
        stmt = stmt.where(Alert.shipment_id == shipment_id)
    if search:
        pattern = like_pattern(search.strip())
        stmt = stmt.where(
            or_(
                Shipment.tracking_id.ilike(pattern, escape="\\"),
                Shipment.customer_name.ilike(pattern, escape="\\"),
                Alert.message.ilike(pattern, escape="\\"),
            )
        )
    total = count_rows(db, stmt)
    stmt = stmt.order_by(
        case((Alert.status == AlertStatus.ACTIVE.value, 0), else_=1),
        severity_rank_expr().desc(),
        Alert.created_at.desc(),
        Alert.id.desc(),
    )
    alerts = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return Page[AlertRead](
        items=[AlertRead.model_validate(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


def top_active_alerts(db: Session, limit: int = 8) -> list[AlertRead]:
    alerts = db.scalars(
        _alert_query()
        .where(Alert.status == AlertStatus.ACTIVE.value)
        .order_by(severity_rank_expr().desc(), Alert.created_at.desc())
        .limit(limit)
    ).all()
    return [AlertRead.model_validate(a) for a in alerts]


def get_alert(db: Session, alert_id: int) -> Alert:
    alert = db.scalars(_alert_query().where(Alert.id == alert_id)).first()
    if alert is None:
        raise NotFoundError(f"Alert {alert_id} not found")
    return alert


def resolve_alert_by_id(db: Session, alert_id: int, note: str | None, resolved_by: str = "user") -> AlertRead:
    alert = get_alert(db, alert_id)
    if alert.status == AlertStatus.RESOLVED.value:
        raise ConflictError(f"Alert {alert_id} is already resolved")
    resolve_alert(alert, note=note or "Resolved manually", resolved_by=resolved_by)
    db.commit()
    return AlertRead.model_validate(get_alert(db, alert_id))


def alert_counts(db: Session) -> AlertCounts:
    rows = db.execute(
        select(Alert.status, Alert.severity, func.count(Alert.id)).group_by(Alert.status, Alert.severity)
    ).all()
    active = sum(c for s, _, c in rows if s == AlertStatus.ACTIVE.value)
    resolved = sum(c for s, _, c in rows if s == AlertStatus.RESOLVED.value)
    by_severity = {s.value: 0 for s in AlertSeverity}
    for status, severity, count in rows:
        if status == AlertStatus.ACTIVE.value:
            by_severity[severity] = count
    return AlertCounts(active=active, resolved=resolved, by_severity=by_severity)

