import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

# Point the application at the test database *before* any app module is imported.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://cargopulse:cargopulse@localhost:5432/cargopulse_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.enums import ShipmentStatus  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Carrier, Route, Shipment, ShipmentStatusHistory  # noqa: E402
from app.utils import utcnow  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Apply migrations to the test DB (down then up, which also proves reversibility)."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE alerts, shipment_status_history, shipments, routes, carriers "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Isolated in-memory Redis for every test (locks, last-scan cache, health)."""
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    getter = lambda: client  # noqa: E731
    import app.api.endpoints.health as health_module
    import app.redis_client as redis_module
    import app.worker.tasks as tasks_module

    monkeypatch.setattr(redis_module, "get_redis", getter)
    monkeypatch.setattr(tasks_module, "get_redis", getter)
    monkeypatch.setattr(health_module, "get_redis", getter)
    return client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ----------------------------------------------------------------------------- factories


class Factory:
    def __init__(self, session):
        self.db = session
        self._n = 0

    def _next(self) -> int:
        self._n += 1
        return self._n

    def carrier(self, **kw) -> Carrier:
        n = self._next()
        carrier = Carrier(
            name=kw.pop("name", f"Carrier {n}"),
            code=kw.pop("code", f"C{n:03d}"),
            contact_email=kw.pop("contact_email", f"ops{n}@carrier.example"),
            is_active=kw.pop("is_active", True),
            **kw,
        )
        self.db.add(carrier)
        self.db.commit()
        return carrier

    def route(self, **kw) -> Route:
        n = self._next()
        route = Route(
            code=kw.pop("code", f"R{n:03d}-LANE"),
            origin_city=kw.pop("origin_city", f"Origin{n}"),
            origin_country=kw.pop("origin_country", "US"),
            destination_city=kw.pop("destination_city", f"Dest{n}"),
            destination_country=kw.pop("destination_country", "CA"),
            mode=kw.pop("mode", "road"),
            distance_km=kw.pop("distance_km", 900),
            estimated_transit_days=kw.pop("estimated_transit_days", 3),
            is_active=kw.pop("is_active", True),
            **kw,
        )
        self.db.add(route)
        self.db.commit()
        return route

    def shipment(self, carrier=None, route=None, **kw) -> Shipment:
        n = self._next()
        carrier = carrier or self.carrier()
        route = route or self.route()
        now = utcnow()
        status = kw.pop("status", ShipmentStatus.IN_TRANSIT.value)
        eta = kw.pop("eta", now + timedelta(days=2))
        shipped_at = kw.pop("shipped_at", min(now - timedelta(days=2), eta - timedelta(days=1)))
        delivered_at = kw.pop(
            "delivered_at", now - timedelta(hours=1) if status == ShipmentStatus.DELIVERED.value else None
        )
        shipment = Shipment(
            tracking_id=kw.pop("tracking_id", f"TEST-{n:06d}"),
            customer_name=kw.pop("customer_name", f"Customer {n}"),
            carrier_id=carrier.id,
            route_id=route.id,
            status=status,
            priority=kw.pop("priority", "standard"),
            weight_kg=kw.pop("weight_kg", Decimal("100.00")),
            pieces=kw.pop("pieces", 1),
            shipped_at=shipped_at,
            eta=eta,
            delivered_at=delivered_at,
            **kw,
        )
        self.db.add(shipment)
        self.db.flush()
        self.db.add(
            ShipmentStatusHistory(
                shipment_id=shipment.id, from_status=None, to_status=status, note="Shipment created"
            )
        )
        self.db.commit()
        return shipment


@pytest.fixture
def factory(db):
    return Factory(db)
