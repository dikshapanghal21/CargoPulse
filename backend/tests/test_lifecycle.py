from datetime import timedelta

from app.models import Alert
from app.services.alert_service import detect_overdue_shipments
from app.utils import utcnow


def post_status(client, sid, **payload):
    return client.post(f"/api/shipments/{sid}/status", json=payload)


def test_full_lifecycle_records_history(client, factory):
    s = factory.shipment(status="pending")
    for status, location in [
        ("picked_up", "Frankfurt, DE"),
        ("in_transit", "Leipzig hub"),
        ("out_for_delivery", "Chicago, US"),
    ]:
        res = post_status(client, s.id, status=status, location=location, note=f"to {status}")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == status
        assert res.json()["current_location"] == location

    res = post_status(client, s.id, status="delivered")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "delivered"
    assert body["delivered_at"] is not None
    assert body["allowed_transitions"] == []
    history = body["status_history"]  # newest first
    assert [h["to_status"] for h in history] == [
        "delivered", "out_for_delivery", "in_transit", "picked_up", "pending",
    ]
    assert [h["from_status"] for h in history] == [
        "out_for_delivery", "in_transit", "picked_up", "pending", None,
    ]
    assert history[1]["note"] == "to out_for_delivery"

    hist = client.get(f"/api/shipments/{s.id}/history")
    assert hist.status_code == 200 and len(hist.json()) == 5


def test_invalid_transition_is_conflict(client, factory):
    s = factory.shipment(status="pending")
    res = post_status(client, s.id, status="delivered")
    assert res.status_code == 409
    assert "Allowed" in res.json()["detail"]
    assert post_status(client, s.id, status="pending").status_code == 409  # no-op transition


def test_terminal_states_are_final(client, factory):
    s = factory.shipment(status="cancelled")
    assert post_status(client, s.id, status="in_transit").status_code == 409
    d = factory.shipment(status="delivered")
    assert post_status(client, d.id, status="delayed").status_code == 409


def test_status_validation(client, factory):
    s = factory.shipment(status="in_transit")
    assert post_status(client, s.id, status="unknown").status_code == 422
    assert post_status(client, s.id, status="in_transit", delivered_at=utcnow().isoformat()).status_code == 422
    future = (utcnow() + timedelta(days=1)).isoformat()
    assert post_status(client, s.id, status="delivered", delivered_at=future).status_code == 422
    before_ship = (s.shipped_at - timedelta(days=1)).isoformat()
    assert post_status(client, s.id, status="delayed", eta=before_ship).status_code == 422
    assert post_status(client, 99999, status="delayed").status_code == 404


def test_leaving_delayed_requires_future_eta(client, factory):
    s = factory.shipment(status="delayed", eta=utcnow() - timedelta(hours=3))
    res = post_status(client, s.id, status="in_transit")
    assert res.status_code == 422
    assert res.json()["field"] == "eta"
    new_eta = utcnow() + timedelta(days=1)
    res = post_status(client, s.id, status="in_transit", eta=new_eta.isoformat(), note="Rebooked")
    assert res.status_code == 200
    body = res.json()
    assert body["is_overdue"] is False
    assert "ETA revised" in body["status_history"][0]["note"]


def test_delivery_resolves_active_overdue_alert(client, factory, db):
    s = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=10))
    scan = detect_overdue_shipments(db)
    assert scan.alerts_created == 1

    res = post_status(client, s.id, status="delivered", note="Signed by J. Doe")
    assert res.status_code == 200
    alerts = res.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["status"] == "resolved"
    assert alerts[0]["resolution_note"] == "Auto-resolved: shipment delivered"
    db.expire_all()
    assert db.query(Alert).filter_by(status="active").count() == 0


def test_revising_eta_via_patch_resolves_alert(client, factory, db):
    s = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=2))
    detect_overdue_shipments(db)
    res = client.patch(f"/api/shipments/{s.id}", json={"eta": (utcnow() + timedelta(days=2)).isoformat()})
    assert res.status_code == 200
    alert = res.json()["alerts"][0]
    assert alert["status"] == "resolved"
    assert alert["resolution_note"].startswith("Auto-resolved: ETA revised")
