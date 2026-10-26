import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.enums import ACTIVE_STATUSES, TransportMode, values
from app.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models import Route, Shipment
from app.schemas.common import Page
from app.schemas.route import RouteCreate, RouteRead, RouteUpdate
from app.services.common import count_rows, like_pattern
from app.utils import page_count

MODE_CODES = {
    TransportMode.ROAD: "RD",
    TransportMode.RAIL: "RL",
    TransportMode.AIR: "AIR",
    TransportMode.OCEAN: "OCN",
}


def _city_code(city: str) -> str:
    letters = re.sub(r"[^A-Za-z0-9]", "", city).upper()
    return (letters[:3] or "XXX").ljust(3, "X")


def _generate_code(db: Session, origin: str, destination: str, mode: TransportMode) -> str:
    base = f"{_city_code(origin)}-{_city_code(destination)}-{MODE_CODES[TransportMode(mode)]}"
    candidate, n = base, 2
    while db.execute(select(Route.id).where(Route.code == candidate)).first():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _stats_subquery():
    return (
        select(
            Shipment.route_id.label("route_id"),
            func.count(Shipment.id).label("total"),
            func.count(Shipment.id).filter(Shipment.status.in_(values(ACTIVE_STATUSES))).label("active"),
        )
        .group_by(Shipment.route_id)
        .subquery()
    )


def _with_stats():
    stats = _stats_subquery()
    return select(
        Route, func.coalesce(stats.c.total, 0), func.coalesce(stats.c.active, 0)
    ).outerjoin(stats, stats.c.route_id == Route.id)


def _to_read(row) -> RouteRead:
    route, total, active = row
    data = RouteRead.model_validate(route)
    data.total_shipments = total
    data.active_shipments = active
    return data


def list_routes(
    db: Session,
    *,
    search: str | None = None,
    mode: TransportMode | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[RouteRead]:
    stmt = _with_stats()
    if search:
        pattern = like_pattern(search.strip())
        stmt = stmt.where(
            or_(
                Route.code.ilike(pattern, escape="\\"),
                Route.origin_city.ilike(pattern, escape="\\"),
                Route.destination_city.ilike(pattern, escape="\\"),
                Route.origin_country.ilike(pattern, escape="\\"),
                Route.destination_country.ilike(pattern, escape="\\"),
            )
        )
    if mode is not None:
        stmt = stmt.where(Route.mode == mode.value)
    if is_active is not None:
        stmt = stmt.where(Route.is_active.is_(is_active))
    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(Route.origin_city, Route.destination_city, Route.mode)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page[RouteRead](
        items=[_to_read(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


def get_route(db: Session, route_id: int) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise NotFoundError(f"Route {route_id} not found")
    return route


def get_route_read(db: Session, route_id: int) -> RouteRead:
    row = db.execute(_with_stats().where(Route.id == route_id)).first()
    if row is None:
        raise NotFoundError(f"Route {route_id} not found")
    return _to_read(row)


def _ensure_unique_lane(db: Session, lane: dict, exclude_id: int | None = None) -> None:
    stmt = select(Route.id).where(
        func.lower(Route.origin_city) == lane["origin_city"].lower(),
        Route.origin_country == lane["origin_country"],
        func.lower(Route.destination_city) == lane["destination_city"].lower(),
        Route.destination_country == lane["destination_country"],
        Route.mode == str(lane["mode"]),
    )
    if exclude_id:
        stmt = stmt.where(Route.id != exclude_id)
    if db.execute(stmt).first():
        raise ConflictError("A route for this origin, destination and mode already exists")


def _ensure_unique_code(db: Session, code: str, exclude_id: int | None = None) -> None:
    stmt = select(Route.id).where(Route.code == code)
    if exclude_id:
        stmt = stmt.where(Route.id != exclude_id)
    if db.execute(stmt).first():
        raise ConflictError(f"Route code '{code}' is already in use", field="code")


def create_route(db: Session, data: RouteCreate) -> RouteRead:
    payload = data.model_dump()
    payload["mode"] = data.mode.value
    _ensure_unique_lane(db, payload)
    if payload.get("code"):
        _ensure_unique_code(db, payload["code"])
    else:
        payload["code"] = _generate_code(db, data.origin_city, data.destination_city, data.mode)
    route = Route(**payload)
    db.add(route)
    db.commit()
    return get_route_read(db, route.id)


def update_route(db: Session, route_id: int, data: RouteUpdate) -> RouteRead:
    route = get_route(db, route_id)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if "mode" in changes:
        changes["mode"] = TransportMode(changes["mode"]).value
    lane = {
        key: changes.get(key, getattr(route, key))
        for key in ("origin_city", "origin_country", "destination_city", "destination_country", "mode")
    }
    if (
        lane["origin_city"].lower() == lane["destination_city"].lower()
        and lane["origin_country"] == lane["destination_country"]
    ):
        raise BusinessValidationError("Origin and destination must be different")
    if any(k in changes for k in lane):
        _ensure_unique_lane(db, lane, exclude_id=route_id)
    if "code" in changes:
        _ensure_unique_code(db, changes["code"], exclude_id=route_id)
    for key, value in changes.items():
        setattr(route, key, value)
    db.commit()
    return get_route_read(db, route_id)


def delete_route(db: Session, route_id: int) -> None:
    route = get_route(db, route_id)
    in_use = db.execute(
        select(func.count(Shipment.id)).where(Shipment.route_id == route_id)
    ).scalar_one()
    if in_use:
        raise ConflictError(
            f"Route {route.code} is used by {in_use} shipment(s) and cannot be deleted. "
            "Deactivate it instead."
        )
    db.delete(route)
    db.commit()
