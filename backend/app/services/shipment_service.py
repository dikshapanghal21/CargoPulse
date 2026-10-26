from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload, selectinload

from app.enums import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    ShipmentPriority,
    ShipmentStatus,
    TransportMode,
    values,
)
from app.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models import Carrier, Route, Shipment
from app.schemas.common import Page
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentDetail,
    ShipmentRead,
    ShipmentUpdate,
    StatusUpdate,
)
from app.services import alert_service
from app.services.common import count_rows, like_pattern
from app.services.lifecycle import allowed_transitions, apply_transition, record_initial_status
from app.utils import ensure_aware, generate_tracking_id, page_count, utcnow


class ShipmentSortField(StrEnum):
    TRACKING_ID = "tracking_id"
    CUSTOMER_NAME = "customer_name"
    STATUS = "status"
    PRIORITY = "priority"
    ETA = "eta"
    SHIPPED_AT = "shipped_at"
    CREATED_AT = "created_at"
    WEIGHT_KG = "weight_kg"
    CARRIER = "carrier"
    ORIGIN = "origin"
    DESTINATION = "destination"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


SORT_COLUMNS = {
    ShipmentSortField.TRACKING_ID: Shipment.tracking_id,
    ShipmentSortField.CUSTOMER_NAME: Shipment.customer_name,
    ShipmentSortField.STATUS: Shipment.status,
    ShipmentSortField.PRIORITY: Shipment.priority,
    ShipmentSortField.ETA: Shipment.eta,
    ShipmentSortField.SHIPPED_AT: Shipment.shipped_at,
    ShipmentSortField.CREATED_AT: Shipment.created_at,
    ShipmentSortField.WEIGHT_KG: Shipment.weight_kg,
    ShipmentSortField.CARRIER: Carrier.name,
    ShipmentSortField.ORIGIN: Route.origin_city,
    ShipmentSortField.DESTINATION: Route.destination_city,
}

NON_NULLABLE_UPDATE_FIELDS = {
    "tracking_id",
    "customer_name",
    "carrier_id",
    "route_id",
    "priority",
    "weight_kg",
    "pieces",
    "shipped_at",
    "eta",
}


@dataclass
class ShipmentFilters:
    search: str | None = None
    statuses: list[ShipmentStatus] | None = None
    carrier_id: int | None = None
    route_id: int | None = None
    priority: ShipmentPriority | None = None
    mode: TransportMode | None = None
    overdue: bool | None = None
    eta_from: datetime | None = None
    eta_to: datetime | None = None


def _base_query():
    return (
        select(Shipment)
        .join(Shipment.carrier)
        .join(Shipment.route)
        .options(contains_eager(Shipment.carrier), contains_eager(Shipment.route))
    )


def overdue_condition(now: datetime):
    return and_(Shipment.status.in_(values(ACTIVE_STATUSES)), Shipment.eta < now)


def _apply_filters(stmt, f: ShipmentFilters, now: datetime):
    if f.search:
        pattern = like_pattern(f.search.strip())
        stmt = stmt.where(
            or_(
                Shipment.tracking_id.ilike(pattern, escape="\\"),
                Shipment.customer_name.ilike(pattern, escape="\\"),
                Shipment.reference.ilike(pattern, escape="\\"),
                Route.origin_city.ilike(pattern, escape="\\"),
                Route.destination_city.ilike(pattern, escape="\\"),
                Route.code.ilike(pattern, escape="\\"),
                Carrier.name.ilike(pattern, escape="\\"),
            )
        )
    if f.statuses:
        stmt = stmt.where(Shipment.status.in_(values(f.statuses)))
    if f.carrier_id:
        stmt = stmt.where(Shipment.carrier_id == f.carrier_id)
    if f.route_id:
        stmt = stmt.where(Shipment.route_id == f.route_id)
    if f.priority:
        stmt = stmt.where(Shipment.priority == f.priority.value)
    if f.mode:
        stmt = stmt.where(Route.mode == f.mode.value)
    if f.overdue is True:
        stmt = stmt.where(overdue_condition(now))
    elif f.overdue is False:
        stmt = stmt.where(not_(overdue_condition(now)))
    if f.eta_from:
        stmt = stmt.where(Shipment.eta >= ensure_aware(f.eta_from))
    if f.eta_to:
        stmt = stmt.where(Shipment.eta <= ensure_aware(f.eta_to))
    return stmt


def list_shipments(
    db: Session,
    filters: ShipmentFilters,
    *,
    sort_by: ShipmentSortField = ShipmentSortField.CREATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
    page: int = 1,
    page_size: int = 20,
) -> Page[ShipmentRead]:
    now = utcnow()
    stmt = _apply_filters(_base_query(), filters, now)
    total = count_rows(db, stmt)
    column = SORT_COLUMNS[sort_by]
    ordering = column.asc() if sort_order == SortOrder.ASC else column.desc()
    tiebreak = Shipment.id.asc() if sort_order == SortOrder.ASC else Shipment.id.desc()
    rows = db.scalars(
        stmt.order_by(ordering.nulls_last(), tiebreak).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page[ShipmentRead](
        items=[ShipmentRead.model_validate(s) for s in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


def get_shipment(db: Session, shipment_id: int) -> Shipment:
    shipment = db.scalars(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(joinedload(Shipment.carrier), joinedload(Shipment.route))
    ).first()
    if shipment is None:
        raise NotFoundError(f"Shipment {shipment_id} not found")
    return shipment


def _detail_query():
    return select(Shipment).options(
        joinedload(Shipment.carrier),
        joinedload(Shipment.route),
        selectinload(Shipment.status_history),
        selectinload(Shipment.alerts),
    )


def _to_detail(shipment: Shipment) -> ShipmentDetail:
    detail = ShipmentDetail.model_validate(shipment)
    detail.allowed_transitions = allowed_transitions(shipment.status)
    return detail


def get_shipment_detail(db: Session, shipment_id: int) -> ShipmentDetail:
    db.expire_all()
    shipment = db.scalars(_detail_query().where(Shipment.id == shipment_id)).first()
    if shipment is None:
        raise NotFoundError(f"Shipment {shipment_id} not found")
    return _to_detail(shipment)


def get_shipment_by_tracking(db: Session, tracking_id: str) -> ShipmentDetail:
    shipment = db.scalars(
        _detail_query().where(Shipment.tracking_id == tracking_id.strip().upper())
    ).first()
    if shipment is None:
        raise NotFoundError(f"No shipment with tracking ID '{tracking_id}'")
    return _to_detail(shipment)


def _require_carrier(db: Session, carrier_id: int) -> Carrier:
    carrier = db.get(Carrier, carrier_id)
    if carrier is None:
        raise BusinessValidationError(f"Carrier {carrier_id} does not exist", field="carrier_id")
    if not carrier.is_active:
        raise BusinessValidationError(f"Carrier '{carrier.name}' is inactive", field="carrier_id")
    return carrier


def _require_route(db: Session, route_id: int) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise BusinessValidationError(f"Route {route_id} does not exist", field="route_id")
    if not route.is_active:
        raise BusinessValidationError(f"Route {route.code} is inactive", field="route_id")
    return route


def _tracking_exists(db: Session, tracking_id: str, exclude_id: int | None = None) -> bool:
    stmt = select(Shipment.id).where(Shipment.tracking_id == tracking_id)
    if exclude_id:
        stmt = stmt.where(Shipment.id != exclude_id)
    return db.execute(stmt).first() is not None


def _new_tracking_id(db: Session) -> str:
    for _ in range(10):
        candidate = generate_tracking_id()
        if not _tracking_exists(db, candidate):
            return candidate
    raise ConflictError("Could not allocate a unique tracking ID; please retry")


def create_shipment(db: Session, data: ShipmentCreate, *, changed_by: str = "user") -> ShipmentDetail:
    _require_carrier(db, data.carrier_id)
    route = _require_route(db, data.route_id)

    if data.tracking_id:
        if _tracking_exists(db, data.tracking_id):
            raise ConflictError(
                f"Tracking ID '{data.tracking_id}' is already in use", field="tracking_id"
            )
        tracking_id = data.tracking_id
    else:
        tracking_id = _new_tracking_id(db)

    now = utcnow()
    shipped_at = data.shipped_at or now
    eta = data.eta or shipped_at + timedelta(days=route.estimated_transit_days)
    if eta <= shipped_at:
        raise BusinessValidationError("ETA must be later than the shipped date", field="eta")

    delivered_at = None
    if data.status == ShipmentStatus.DELIVERED:
        delivered_at = data.delivered_at or now
        if delivered_at < shipped_at:
            raise BusinessValidationError(
                "delivered_at cannot be earlier than the shipped date", field="delivered_at"
            )

    shipment = Shipment(
        tracking_id=tracking_id,
        reference=data.reference,
        customer_name=data.customer_name,
        description=data.description,
        carrier_id=data.carrier_id,
        route_id=data.route_id,
        status=data.status.value,
        priority=data.priority.value,
        weight_kg=data.weight_kg,
        pieces=data.pieces,
        current_location=data.current_location
        or (f"{route.origin_city}, {route.origin_country}" if data.status != ShipmentStatus.DELIVERED
            else f"{route.destination_city}, {route.destination_country}"),
        shipped_at=shipped_at,
        eta=eta,
        delivered_at=delivered_at,
    )
    db.add(shipment)
    db.flush()
    record_initial_status(db, shipment, changed_by=changed_by, at=now)
    db.commit()
    return get_shipment_detail(db, shipment.id)


def update_shipment(db: Session, shipment_id: int, data: ShipmentUpdate) -> ShipmentDetail:
    shipment = get_shipment(db, shipment_id)
    changes = data.model_dump(exclude_unset=True)

    for key in NON_NULLABLE_UPDATE_FIELDS:
        if key in changes and changes[key] is None:
            raise BusinessValidationError(f"'{key}' cannot be null", field=key)

    logistics_fields = {"carrier_id", "route_id", "shipped_at", "eta"}
    if shipment.status in values(TERMINAL_STATUSES) and logistics_fields & {
        k for k, v in changes.items() if v != getattr(shipment, k)
    }:
        raise ConflictError(
            f"Carrier, route and dates of a {shipment.status} shipment can no longer be changed"
        )

    if "tracking_id" in changes and changes["tracking_id"] != shipment.tracking_id:
        if _tracking_exists(db, changes["tracking_id"], exclude_id=shipment_id):
            raise ConflictError(
                f"Tracking ID '{changes['tracking_id']}' is already in use", field="tracking_id"
            )
    if "carrier_id" in changes and changes["carrier_id"] != shipment.carrier_id:
        _require_carrier(db, changes["carrier_id"])
    if "route_id" in changes and changes["route_id"] != shipment.route_id:
        _require_route(db, changes["route_id"])

    shipped_at = changes.get("shipped_at", ensure_aware(shipment.shipped_at))
    eta = changes.get("eta", ensure_aware(shipment.eta))
    if eta <= shipped_at:
        raise BusinessValidationError("ETA must be later than the shipped date", field="eta")
    if shipment.delivered_at and ensure_aware(shipment.delivered_at) < shipped_at:
        raise BusinessValidationError(
            "Shipped date cannot be later than the delivery date", field="shipped_at"
        )

    for key, value in changes.items():
        if key == "priority" and value is not None:
            value = ShipmentPriority(value).value
        setattr(shipment, key, value)
    db.flush()
    if "eta" in changes:
        alert_service.resolve_stale_alerts_for_shipment(db, shipment)
    db.commit()
    return get_shipment_detail(db, shipment_id)


def change_status(
    db: Session, shipment_id: int, payload: StatusUpdate, *, changed_by: str = "user"
) -> ShipmentDetail:
    shipment = get_shipment(db, shipment_id)
    now = utcnow()
    target = payload.status

    shipped_at = ensure_aware(shipment.shipped_at)
    if payload.eta is not None:
        if payload.eta <= shipped_at:
            raise BusinessValidationError("ETA must be later than the shipped date", field="eta")
        if target in TERMINAL_STATUSES:
            raise BusinessValidationError(
                "ETA cannot be revised when completing or cancelling a shipment", field="eta"
            )

    new_eta = payload.eta or ensure_aware(shipment.eta)
    leaving_delay = (
        shipment.status == ShipmentStatus.DELAYED.value
        and target not in TERMINAL_STATUSES
        and target != ShipmentStatus.DELAYED
    )
    if leaving_delay and new_eta <= now:
        raise BusinessValidationError(
            "This shipment is past its ETA. Provide a revised future ETA to move it out of 'delayed'.",
            field="eta",
        )

    if target == ShipmentStatus.DELIVERED:
        delivered_at = payload.delivered_at or now
        if delivered_at < shipped_at:
            raise BusinessValidationError(
                "delivered_at cannot be earlier than the shipped date", field="delivered_at"
            )
    location = payload.location
    if target == ShipmentStatus.DELIVERED and not location:
        location = f"{shipment.route.destination_city}, {shipment.route.destination_country}"

    note = payload.note
    if payload.eta is not None and payload.eta != ensure_aware(shipment.eta):
        eta_note = f"ETA revised to {payload.eta:%Y-%m-%d %H:%M} UTC"
        note = f"{note} — {eta_note}" if note else eta_note

    apply_transition(
        db, shipment, target, note=note, location=location, changed_by=changed_by, at=now
    )
    if payload.eta is not None:
        shipment.eta = payload.eta
    if target == ShipmentStatus.DELIVERED:
        shipment.delivered_at = delivered_at
    db.flush()
    alert_service.resolve_stale_alerts_for_shipment(db, shipment, now=now)
    db.commit()
    return get_shipment_detail(db, shipment_id)


def delete_shipment(db: Session, shipment_id: int) -> None:
    shipment = get_shipment(db, shipment_id)
    db.delete(shipment)
    db.commit()
