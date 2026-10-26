from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.enums import ACTIVE_STATUSES, ShipmentStatus, values
from app.exceptions import ConflictError, NotFoundError
from app.models import Carrier, Shipment
from app.schemas.carrier import CarrierCreate, CarrierRead, CarrierUpdate
from app.schemas.common import Page
from app.services.common import count_rows, like_pattern, rate
from app.utils import page_count


def _stats_subquery():
    return (
        select(
            Shipment.carrier_id.label("carrier_id"),
            func.count(Shipment.id).label("total"),
            func.count(Shipment.id).filter(Shipment.status.in_(values(ACTIVE_STATUSES))).label("active"),
            func.count(Shipment.id)
            .filter(Shipment.status == ShipmentStatus.DELAYED.value)
            .label("delayed"),
            func.count(Shipment.id)
            .filter(Shipment.status == ShipmentStatus.DELIVERED.value)
            .label("delivered"),
            func.count(Shipment.id)
            .filter(
                and_(
                    Shipment.status == ShipmentStatus.DELIVERED.value,
                    Shipment.delivered_at <= Shipment.eta,
                )
            )
            .label("on_time"),
        )
        .group_by(Shipment.carrier_id)
        .subquery()
    )


def _with_stats():
    stats = _stats_subquery()
    stmt = select(
        Carrier,
        func.coalesce(stats.c.total, 0),
        func.coalesce(stats.c.active, 0),
        func.coalesce(stats.c.delayed, 0),
        func.coalesce(stats.c.delivered, 0),
        func.coalesce(stats.c.on_time, 0),
    ).outerjoin(stats, stats.c.carrier_id == Carrier.id)
    return stmt


def _to_read(row) -> CarrierRead:
    carrier, total, active, delayed, delivered, on_time = row
    data = CarrierRead.model_validate(carrier)
    data.total_shipments = total
    data.active_shipments = active
    data.delayed_shipments = delayed
    data.on_time_rate = rate(on_time, delivered)
    return data


def list_carriers(
    db: Session,
    *,
    search: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[CarrierRead]:
    stmt = _with_stats()
    if search:
        pattern = like_pattern(search.strip())
        stmt = stmt.where(
            or_(
                Carrier.name.ilike(pattern, escape="\\"),
                Carrier.code.ilike(pattern, escape="\\"),
                Carrier.contact_email.ilike(pattern, escape="\\"),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Carrier.is_active.is_(is_active))
    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(Carrier.name.asc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page[CarrierRead](
        items=[_to_read(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


def get_carrier(db: Session, carrier_id: int) -> Carrier:
    carrier = db.get(Carrier, carrier_id)
    if carrier is None:
        raise NotFoundError(f"Carrier {carrier_id} not found")
    return carrier


def get_carrier_read(db: Session, carrier_id: int) -> CarrierRead:
    row = db.execute(_with_stats().where(Carrier.id == carrier_id)).first()
    if row is None:
        raise NotFoundError(f"Carrier {carrier_id} not found")
    return _to_read(row)


def _ensure_unique(db: Session, *, name: str | None, code: str | None, exclude_id: int | None = None):
    if name is not None:
        stmt = select(Carrier.id).where(func.lower(Carrier.name) == name.lower())
        if exclude_id:
            stmt = stmt.where(Carrier.id != exclude_id)
        if db.execute(stmt).first():
            raise ConflictError(f"A carrier named '{name}' already exists", field="name")
    if code is not None:
        stmt = select(Carrier.id).where(Carrier.code == code)
        if exclude_id:
            stmt = stmt.where(Carrier.id != exclude_id)
        if db.execute(stmt).first():
            raise ConflictError(f"Carrier code '{code}' is already in use", field="code")


def create_carrier(db: Session, data: CarrierCreate) -> CarrierRead:
    _ensure_unique(db, name=data.name, code=data.code)
    carrier = Carrier(**data.model_dump())
    db.add(carrier)
    db.commit()
    return get_carrier_read(db, carrier.id)


def update_carrier(db: Session, carrier_id: int, data: CarrierUpdate) -> CarrierRead:
    carrier = get_carrier(db, carrier_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "code", "is_active"):
        if required in changes and changes[required] is None:
            changes.pop(required)
    _ensure_unique(db, name=changes.get("name"), code=changes.get("code"), exclude_id=carrier_id)
    for key, value in changes.items():
        setattr(carrier, key, value)
    db.commit()
    return get_carrier_read(db, carrier_id)


def delete_carrier(db: Session, carrier_id: int) -> None:
    carrier = get_carrier(db, carrier_id)
    in_use = db.execute(
        select(func.count(Shipment.id)).where(Shipment.carrier_id == carrier_id)
    ).scalar_one()
    if in_use:
        raise ConflictError(
            f"Carrier '{carrier.name}' is assigned to {in_use} shipment(s) and cannot be deleted. "
            "Deactivate it instead."
        )
    db.delete(carrier)
    db.commit()
