from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.enums import AlertSeverity
from app.models import Alert, Shipment, ShipmentStatusHistory
from app.services.alert_service import (
    SYSTEM_ACTOR,
    detect_overdue_shipments,
    overdue_dedupe_key,
    severity_for,
)
from app.utils import utcnow
from app.worker import tasks
from app.worker.celery_app import OVERDUE_TASK_NAME, celery_app


def active_alerts(db):
    db.expire_all()
    return db.query(Alert).filter_by(status="active").all()


class TestDetection:
    def test_flags_overdue_shipment(self, db, factory):
        s = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=8))
        on_time = factory.shipment(status="in_transit", eta=utcnow() + timedelta(hours=8))
        factory.shipment(status="delivered", eta=utcnow() - timedelta(days=1))
        factory.shipment(status="cancelled", eta=utcnow() - timedelta(days=1))

        result = detect_overdue_shipments(db)
        assert result.overdue_found == 1
        assert result.alerts_created == 1
        assert result.shipments_marked_delayed == 1

        alerts = active_alerts(db)
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.shipment_id == s.id
        assert alert.alert_type == "overdue"
        assert alert.severity == AlertSeverity.MEDIUM.value
        assert s.tracking_id in alert.message
        assert alert.dedupe_key == overdue_dedupe_key(db.get(Shipment, s.id))

        refreshed = db.get(Shipment, s.id)
        assert refreshed.status == "delayed"
        assert db.get(Shipment, on_time.id).status == "in_transit"
        last = (
            db.query(ShipmentStatusHistory)
            .filter_by(shipment_id=s.id)
            .order_by(ShipmentStatusHistory.id.desc())
            .first()
        )
        assert (last.from_status, last.to_status, last.changed_by) == ("in_transit", "delayed", SYSTEM_ACTOR)

    def test_repeated_scans_do_not_duplicate(self, db, factory):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=2))
        factory.shipment(status="pending", eta=utcnow() - timedelta(hours=1))
        first = detect_overdue_shipments(db)
        assert first.alerts_created == 2
        for _ in range(3):
            again = detect_overdue_shipments(db)
            assert again.alerts_created == 0
            assert again.duplicates_skipped == 2
            assert again.shipments_marked_delayed == 0
        assert db.query(Alert).count() == 2
        # Exactly one automatic 'delayed' transition per shipment.
        assert db.query(ShipmentStatusHistory).filter_by(to_status="delayed").count() == 2

    def test_manually_resolved_alert_is_not_recreated_for_same_eta(self, db, factory, client):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=3))
        detect_overdue_shipments(db)
        alert_id = active_alerts(db)[0].id
        assert client.post(f"/api/alerts/{alert_id}/resolve", json={"note": "Carrier notified"}).status_code == 200

        result = detect_overdue_shipments(db)
        assert result.alerts_created == 0
        assert result.duplicates_skipped == 1
        assert active_alerts(db) == []
        assert db.query(Alert).count() == 1

    def test_revised_but_still_past_eta_supersedes_alert(self, db, factory):
        s = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=10))
        detect_overdue_shipments(db)
        db.get(Shipment, s.id).eta = utcnow() - timedelta(hours=1)
        db.commit()

        result = detect_overdue_shipments(db)
        assert result.alerts_resolved == 1
        assert result.alerts_created == 1
        alerts = db.query(Alert).order_by(Alert.id).all()
        assert [a.status for a in alerts] == ["resolved", "active"]
        assert alerts[0].resolution_note == "Superseded: ETA revised but still overdue"

    def test_auto_resolves_when_eta_moves_forward_or_delivered(self, db, factory):
        a = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=4))
        b = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=4))
        detect_overdue_shipments(db)
        assert len(active_alerts(db)) == 2

        sa = db.get(Shipment, a.id)
        sa.eta = utcnow() + timedelta(days=1)
        sb = db.get(Shipment, b.id)
        sb.status = "delivered"
        sb.delivered_at = utcnow()
        db.commit()

        result = detect_overdue_shipments(db)
        assert result.alerts_resolved == 2
        assert result.alerts_created == 0
        db.expire_all()
        notes = sorted(x.resolution_note for x in db.query(Alert).all())
        assert notes[0] == "Auto-resolved: ETA revised to " + f"{sa.eta:%Y-%m-%d %H:%M} UTC"
        assert notes[1] == "Auto-resolved: shipment delivered"
        assert all(x.resolved_by == SYSTEM_ACTOR and x.resolved_at for x in db.query(Alert).all())

    def test_severity_escalates_without_new_alert(self, db, factory):
        s = factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=1))
        detect_overdue_shipments(db)
        assert active_alerts(db)[0].severity == "low"
        later = utcnow() + timedelta(hours=30)
        result = detect_overdue_shipments(db, now=later)
        assert result.alerts_escalated == 1 and result.alerts_created == 0
        alerts = active_alerts(db)
        assert len(alerts) == 1 and alerts[0].severity == "high" and alerts[0].shipment_id == s.id

    def test_grace_period(self, db, factory):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(minutes=10))
        assert detect_overdue_shipments(db, grace_minutes=30).alerts_created == 0
        assert detect_overdue_shipments(db, grace_minutes=5).alerts_created == 1

    @pytest.mark.parametrize(
        "hours, priority, expected",
        [
            (1, "standard", "low"),
            (10, "standard", "medium"),
            (30, "standard", "high"),
            (100, "standard", "critical"),
            (1, "express", "medium"),
            (1, "critical", "high"),
            (30, "critical", "critical"),
        ],
    )
    def test_severity_rules(self, hours, priority, expected):
        assert severity_for(hours, priority).value == expected


class TestDatabaseGuarantees:
    def test_partial_unique_index_blocks_second_active_alert(self, db, factory):
        s = factory.shipment()
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="low", message="a", dedupe_key="k1"))
        db.commit()
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="low", message="b", dedupe_key="k2"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_resolved_alerts_do_not_block_new_active_alert(self, db, factory):
        s = factory.shipment()
        now = utcnow()
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="low", message="a", dedupe_key="k1",
                     status="resolved", resolved_at=now))
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="low", message="b", dedupe_key="k2"))
        db.commit()
        assert db.query(Alert).count() == 2

    def test_dedupe_key_unique(self, db, factory):
        s = factory.shipment()
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="low", message="a", dedupe_key="same",
                     status="resolved", resolved_at=utcnow()))
        db.commit()
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="low", message="b", dedupe_key="same"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_check_constraints(self, db, factory):
        s = factory.shipment()
        db.add(Alert(shipment_id=s.id, alert_type="overdue", severity="extreme", message="x", dedupe_key="c1"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        shipment = db.get(Shipment, s.id)
        shipment.status = "delivered"  # without delivered_at -> violates constraint
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestCeleryTask:
    def test_task_is_registered_and_scheduled(self):
        assert OVERDUE_TASK_NAME in celery_app.tasks
        entry = celery_app.conf.beat_schedule["detect-overdue-shipments"]
        assert entry["task"] == OVERDUE_TASK_NAME
        assert entry["schedule"] == float(settings.overdue_scan_interval_seconds)
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.broker_url.startswith("redis://")

    def test_task_runs_scan_and_caches_summary(self, db, factory, fake_redis):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=5))
        outcome = tasks.detect_overdue_shipments_task.apply()
        assert outcome.successful()
        result = outcome.get()
        assert result["alerts_created"] == 1 and result["skipped"] is False
        assert fake_redis.get("cargopulse:overdue-scan:last-run") is not None
        assert fake_redis.get(tasks.SCAN_LOCK_KEY) is None  # lock released

        second = tasks.detect_overdue_shipments_task.apply().get()
        assert second["alerts_created"] == 0 and second["duplicates_skipped"] == 1
        assert len(active_alerts(db)) == 1

    def test_concurrent_run_is_skipped_while_lock_held(self, db, factory, fake_redis):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=5))
        lock = fake_redis.lock(tasks.SCAN_LOCK_KEY, timeout=60)
        assert lock.acquire(blocking=False)
        try:
            result = tasks.run_overdue_scan()
            assert result["skipped"] is True
            assert active_alerts(db) == []
        finally:
            lock.release()
        assert tasks.run_overdue_scan()["alerts_created"] == 1

    def test_scan_endpoint_queues_task(self, client, monkeypatch):
        class FakeResult:
            id = "task-123"

        monkeypatch.setattr(tasks.detect_overdue_shipments_task, "apply_async", lambda **kw: FakeResult())
        res = client.post("/api/alerts/scan")
        assert res.status_code == 202
        assert res.json() == {"task_id": "task-123", "status": "queued"}

    def test_scan_endpoint_reports_broker_outage(self, client, monkeypatch):
        def boom(**kw):
            raise ConnectionError("redis down")

        monkeypatch.setattr(tasks.detect_overdue_shipments_task, "apply_async", boom)
        res = client.post("/api/alerts/scan")
        assert res.status_code == 503

    def test_last_scan_endpoint(self, client, factory):
        assert client.get("/api/alerts/scan/last").json()["available"] is False
        tasks.run_overdue_scan()
        body = client.get("/api/alerts/scan/last").json()
        assert body["available"] is True
        assert body["interval_seconds"] == settings.overdue_scan_interval_seconds


class TestAlertApi:
    def test_list_filter_and_order(self, client, db, factory):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=100), customer_name="Late Co")
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=2), customer_name="Bit Late")
        detect_overdue_shipments(db)
        data = client.get("/api/alerts").json()
        assert data["total"] == 2
        assert [a["severity"] for a in data["items"]] == ["critical", "low"]
        assert data["items"][0]["shipment"]["customer_name"] == "Late Co"
        assert client.get("/api/alerts", params={"severity": "low"}).json()["total"] == 1
        assert client.get("/api/alerts", params={"status": "resolved"}).json()["total"] == 0
        assert client.get("/api/alerts", params={"search": "bit late"}).json()["total"] == 1
        assert client.get("/api/alerts", params={"status": "open"}).status_code == 422

        counts = client.get("/api/alerts/counts").json()
        assert counts["active"] == 2 and counts["by_severity"]["critical"] == 1

    def test_resolve_endpoint(self, client, db, factory):
        factory.shipment(status="in_transit", eta=utcnow() - timedelta(hours=2))
        detect_overdue_shipments(db)
        alert_id = active_alerts(db)[0].id
        res = client.post(f"/api/alerts/{alert_id}/resolve", json={"note": "Customer informed"})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "resolved"
        assert body["resolution_note"] == "Customer informed"
        assert body["resolved_by"] == "user"
        assert client.post(f"/api/alerts/{alert_id}/resolve", json={}).status_code == 409
        assert client.post("/api/alerts/9999/resolve", json={}).status_code == 404
