import json
import logging
from datetime import timedelta

from sqlalchemy import Date, and_, cast, func, literal_column, select
from sqlalchemy.orm import Session

from app.enums import (
    ACTIVE_STATUSES,
    IN_TRANSIT_STATUSES,
    AlertSeverity,
    AlertStatus,
    ShipmentStatus,
    values,
)
from app.models import Alert, Carrier, Route, Shipment
from app.schemas.alert import ScanResult
from app.schemas.dashboard import (
    CarrierPerformance,
    DashboardData,
    DashboardSummary,
    ModeCount,
    StatusCount,
    VolumePoint,
)
from app.schemas.shipment import ShipmentRead
from app.services import alert_service
from app.services.common import rate
from app.services.shipment_service import _base_query
from app.utils import utcnow

logger = logging.getLogger(__name__)

LAST_SCAN_KEY = "cargopulse:overdue-scan:last-run"

DELIVERED = ShipmentStatus.DELIVERED.value
on_time_condition = and_(Shipment.status == DELIVERED, Shipment.delivered_at <= Shipment.eta)


def get_summary(db: Session) -> DashboardSummary:
    now = utcnow()
    row = db.execute(
        select(
            func.count(Shipment.id),
            func.count(Shipment.id).filter(Shipment.status.in_(values(IN_TRANSIT_STATUSES))),
            func.count(Shipment.id).filter(Shipment.status == DELIVERED),
            func.count(Shipment.id).filter(Shipment.status == ShipmentStatus.DELAYED.value),
            func.count(Shipment.id).filter(Shipment.status == ShipmentStatus.PENDING.value),
            func.count(Shipment.id).filter(Shipment.status == ShipmentStatus.CANCELLED.value),
            func.count(Shipment.id).filter(
                Shipment.status.in_(values(ACTIVE_STATUSES)), Shipment.eta < now
            ),
            func.count(Shipment.id).filter(on_time_condition),
            func.count(Shipment.id).filter(
                Shipment.status.in_(values(ACTIVE_STATUSES)),
                Shipment.eta >= now,
                Shipment.eta < now + timedelta(days=7),
            ),
        )
    ).one()
    total, in_transit, delivered, delayed, pending, cancelled, overdue, on_time, due_7 = row
    active_alerts, critical_alerts = db.execute(
        select(
            func.count(Alert.id),
            func.count(Alert.id).filter(Alert.severity == AlertSeverity.CRITICAL.value),
        ).where(Alert.status == AlertStatus.ACTIVE.value)
    ).one()
    return DashboardSummary(
        total_shipments=total,
        in_transit=in_transit,
        delivered=delivered,
        delayed=delayed,
        pending=pending,
        cancelled=cancelled,
        overdue=overdue,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
        on_time_rate=rate(on_time, delivered),
        due_next_7_days=due_7,
    )


def get_status_breakdown(db: Session) -> list[StatusCount]:
    counts = dict(
        db.execute(select(Shipment.status, func.count(Shipment.id)).group_by(Shipment.status)).all()
    )
    return [StatusCount(status=s.value, count=counts.get(s.value, 0)) for s in ShipmentStatus]


def get_volume_trend(db: Session, days: int = 30) -> list[VolumePoint]:
    today = utcnow().date()
    start = today - timedelta(days=days - 1)
    series = select(
        cast(
            func.generate_series(start, today, timedelta(days=1)),
            Date,
        ).label("day")
    ).subquery()
    shipped = (
        select(
            cast(func.timezone("UTC", Shipment.shipped_at), Date).label("day"),
            func.count(Shipment.id).label("n"),
        )
        .where(cast(func.timezone("UTC", Shipment.shipped_at), Date) >= start)
        .group_by(literal_column("1"))  # positional: avoids duplicate bind params
        .subquery()
    )
    delivered = (
        select(
            cast(func.timezone("UTC", Shipment.delivered_at), Date).label("day"),
            func.count(Shipment.id).label("n"),
        )
        .where(
            Shipment.delivered_at.is_not(None),
            cast(func.timezone("UTC", Shipment.delivered_at), Date) >= start,
        )
        .group_by(literal_column("1"))
        .subquery()
    )
    rows = db.execute(
        select(
            series.c.day,
            func.coalesce(shipped.c.n, 0),
            func.coalesce(delivered.c.n, 0),
        )
        .outerjoin(shipped, shipped.c.day == series.c.day)
        .outerjoin(delivered, delivered.c.day == series.c.day)
        .order_by(series.c.day)
    ).all()
    return [VolumePoint(date=d, shipped=s, delivered=dl) for d, s, dl in rows]


def get_carrier_performance(db: Session) -> list[CarrierPerformance]:
    rows = db.execute(
        select(
            Carrier.id,
            Carrier.name,
            Carrier.code,
            func.count(Shipment.id),
            func.count(Shipment.id).filter(Shipment.status.in_(values(ACTIVE_STATUSES))),
            func.count(Shipment.id).filter(Shipment.status == DELIVERED),
            func.count(Shipment.id).filter(Shipment.status == ShipmentStatus.DELAYED.value),
            func.count(Shipment.id).filter(on_time_condition),
        )
        .outerjoin(Shipment, Shipment.carrier_id == Carrier.id)
        .group_by(Carrier.id)
        .having(func.count(Shipment.id) > 0)
        .order_by(func.count(Shipment.id).desc(), Carrier.name)
    ).all()
    return [
        CarrierPerformance(
            carrier_id=cid,
            carrier=name,
            code=code,
            total=total,
            active=active,
            delivered=delivered,
            delayed=delayed,
            on_time_rate=rate(on_time, delivered),
        )
        for cid, name, code, total, active, delivered, delayed, on_time in rows
    ]


def get_mode_breakdown(db: Session) -> list[ModeCount]:
    rows = db.execute(
        select(
            Route.mode,
            func.count(Shipment.id),
            func.count(Shipment.id).filter(Shipment.status.in_(values(ACTIVE_STATUSES))),
            func.count(Shipment.id).filter(Shipment.status == ShipmentStatus.DELAYED.value),
            func.count(Shipment.id).filter(Shipment.status == DELIVERED),
            func.count(Shipment.id).filter(on_time_condition),
        )
        .join(Shipment, Shipment.route_id == Route.id)
        .group_by(Route.mode)
        .order_by(func.count(Shipment.id).desc())
    ).all()
    return [
        ModeCount(
            mode=m, count=c, active=active, delayed=delayed, on_time_rate=rate(on_time, delivered)
        )
        for m, c, active, delayed, delivered, on_time in rows
    ]


def get_recent_shipments(db: Session, limit: int = 8) -> list[ShipmentRead]:
    rows = db.scalars(
        _base_query().order_by(Shipment.created_at.desc(), Shipment.id.desc()).limit(limit)
    ).all()
    return [ShipmentRead.model_validate(s) for s in rows]


def get_upcoming_deliveries(db: Session, limit: int = 8, days: int = 7) -> list[ShipmentRead]:
    now = utcnow()
    rows = db.scalars(
        _base_query()
        .where(
            Shipment.status.in_(values(ACTIVE_STATUSES)),
            Shipment.eta >= now,
            Shipment.eta < now + timedelta(days=days),
        )
        .order_by(Shipment.eta.asc())
        .limit(limit)
    ).all()
    return [ShipmentRead.model_validate(s) for s in rows]


def get_last_scan() -> ScanResult | None:
    try:
        from app.redis_client import get_redis

        raw = get_redis().get(LAST_SCAN_KEY)
    except Exception as exc:  # Redis unavailable must not break the dashboard
        logger.warning("Could not read last scan from Redis: %s", exc)
        return None
    if not raw:
        return None
    try:
        return ScanResult.model_validate(json.loads(raw))
    except (ValueError, TypeError):
        return None


def get_dashboard(db: Session, trend_days: int = 30) -> DashboardData:
    return DashboardData(
        summary=get_summary(db),
        status_breakdown=get_status_breakdown(db),
        volume_trend=get_volume_trend(db, trend_days),
        carrier_performance=get_carrier_performance(db),
        mode_breakdown=get_mode_breakdown(db),
        recent_shipments=get_recent_shipments(db),
        upcoming_deliveries=get_upcoming_deliveries(db),
        active_alerts=alert_service.top_active_alerts(db),
        last_scan=get_last_scan(),
    )
