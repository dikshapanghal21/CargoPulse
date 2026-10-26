from datetime import timedelta

from app.services.alert_service import detect_overdue_shipments
from app.utils import utcnow


def build(factory):
    now = utcnow()
    c1 = factory.carrier(name="Alpha", code="ALP")
    c2 = factory.carrier(name="Bravo", code="BRV")
    road = factory.route(mode="road")
    air = factory.route(mode="air")
    # delivered on time (c1) / late (c1) / on time (c2)
    factory.shipment(c1, road, status="delivered", shipped_at=now - timedelta(days=5),
                     eta=now - timedelta(days=2), delivered_at=now - timedelta(days=3))
    factory.shipment(c1, road, status="delivered", shipped_at=now - timedelta(days=5),
                     eta=now - timedelta(days=2), delivered_at=now - timedelta(days=1))
    factory.shipment(c2, air, status="delivered", shipped_at=now - timedelta(days=4),
                     eta=now - timedelta(days=1), delivered_at=now - timedelta(days=1, hours=2))
    # moving
    factory.shipment(c1, road, status="in_transit", eta=now + timedelta(days=1))
    factory.shipment(c2, air, status="picked_up", eta=now + timedelta(days=3))
    factory.shipment(c2, air, status="out_for_delivery", eta=now + timedelta(hours=6))
    factory.shipment(c1, air, status="in_transit", eta=now + timedelta(days=10))
    # overdue but not yet flagged
    factory.shipment(c2, road, status="in_transit", eta=now - timedelta(hours=30), priority="express")
    # other
    factory.shipment(c1, road, status="pending", shipped_at=now - timedelta(hours=1), eta=now + timedelta(days=2))
    factory.shipment(c2, road, status="cancelled", eta=now + timedelta(days=2))
    return c1, c2


def test_summary_metrics_are_computed_from_db(client, factory, db):
    build(factory)
    s = client.get("/api/dashboard/summary").json()
    assert s["total_shipments"] == 10
    assert s["in_transit"] == 5  # picked_up + in_transit + out_for_delivery (incl. the overdue one)
    assert s["delivered"] == 3
    assert s["delayed"] == 0
    assert s["pending"] == 1
    assert s["cancelled"] == 1
    assert s["overdue"] == 1
    assert s["active_alerts"] == 0
    assert s["on_time_rate"] == round(2 / 3 * 100, 1)
    assert s["due_next_7_days"] == 4  # +6h, +1d, +2d (pending), +3d

    # After the background scan the overdue shipment becomes "delayed" with an alert.
    detect_overdue_shipments(db)
    s = client.get("/api/dashboard/summary").json()
    assert s["delayed"] == 1
    assert s["in_transit"] == 4
    assert s["active_alerts"] == 1
    assert s["overdue"] == 1


def test_summary_empty_database(client):
    s = client.get("/api/dashboard/summary").json()
    assert s["total_shipments"] == 0
    assert s["on_time_rate"] is None


def test_full_dashboard_payload(client, factory, db):
    c1, c2 = build(factory)
    detect_overdue_shipments(db)
    data = client.get("/api/dashboard").json()

    breakdown = {row["status"]: row["count"] for row in data["status_breakdown"]}
    assert breakdown == {
        "pending": 1, "picked_up": 1, "in_transit": 2, "out_for_delivery": 1,
        "delayed": 1, "delivered": 3, "cancelled": 1,
    }

    trend = data["volume_trend"]
    assert len(trend) == 30
    assert sum(p["shipped"] for p in trend) == 10
    assert sum(p["delivered"] for p in trend) == 3
    assert trend[-1]["date"] == utcnow().date().isoformat()

    perf = {p["code"]: p for p in data["carrier_performance"]}
    assert perf["ALP"]["total"] == 5 and perf["ALP"]["delivered"] == 2 and perf["ALP"]["on_time_rate"] == 50.0
    assert perf["BRV"]["delayed"] == 1 and perf["BRV"]["on_time_rate"] == 100.0

    modes = {m["mode"]: m for m in data["mode_breakdown"]}
    assert {k: v["count"] for k, v in modes.items()} == {"road": 6, "air": 4}
    assert modes["road"]["active"] == 3 and modes["road"]["delayed"] == 1
    assert modes["road"]["on_time_rate"] == 50.0 and modes["air"]["on_time_rate"] == 100.0

    assert len(data["recent_shipments"]) == 8
    upcoming = data["upcoming_deliveries"]
    assert [u["status"] for u in upcoming] == ["out_for_delivery", "in_transit", "pending", "picked_up"]
    etas = [u["eta"] for u in upcoming]
    assert etas == sorted(etas)

    assert len(data["active_alerts"]) == 1
    assert data["active_alerts"][0]["severity"] == "critical"  # 30h overdue (high) + express bump


def test_dashboard_volume_trend_window(client, factory):
    build(factory)
    res = client.get("/api/dashboard/volume-trend", params={"days": 7})
    assert res.status_code == 200 and len(res.json()) == 7
    assert client.get("/api/dashboard/volume-trend", params={"days": 2}).status_code == 422


def test_dashboard_includes_last_scan_from_redis(client, factory, fake_redis):
    from app.worker.tasks import run_overdue_scan

    build(factory)
    assert client.get("/api/dashboard").json()["last_scan"] is None
    run_overdue_scan()
    last = client.get("/api/dashboard").json()["last_scan"]
    assert last["alerts_created"] == 1 and last["overdue_found"] == 1


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["checks"] == {"database": "ok", "redis": "ok"}
