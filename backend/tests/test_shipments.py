from datetime import timedelta

import pytest

from app.enums import ShipmentStatus
from app.utils import utcnow


def iso(dt):
    return dt.isoformat()


@pytest.fixture
def refs(factory):
    carrier = factory.carrier(name="Meridian Express", code="MEX")
    route = factory.route(
        code="FRA-CHI-AIR", origin_city="Frankfurt", origin_country="DE",
        destination_city="Chicago", destination_country="US", mode="air", estimated_transit_days=2,
    )
    return carrier, route


class TestCreate:
    def test_create_with_defaults(self, client, refs):
        carrier, route = refs
        res = client.post(
            "/api/shipments",
            json={"customer_name": "Acme Corp", "carrier_id": carrier.id, "route_id": route.id, "weight_kg": 120.5},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["tracking_id"].startswith("CP")
        assert body["status"] == "pending"
        assert body["priority"] == "standard"
        assert body["weight_kg"] == 120.5
        assert body["carrier"]["code"] == "MEX"
        assert body["route"]["label"] == "Frankfurt → Chicago"
        assert body["current_location"] == "Frankfurt, DE"
        # ETA derived from the route's transit days.
        from datetime import datetime

        shipped = datetime.fromisoformat(body["shipped_at"])
        eta = datetime.fromisoformat(body["eta"])
        assert eta - shipped == timedelta(days=2)
        assert len(body["status_history"]) == 1
        assert body["status_history"][0]["to_status"] == "pending"
        assert body["status_history"][0]["from_status"] is None
        assert set(body["allowed_transitions"]) == {"picked_up", "delayed", "cancelled"}

    def test_custom_tracking_id_normalised_and_unique(self, client, refs):
        carrier, route = refs
        payload = {"tracking_id": "acme-0001", "customer_name": "Acme", "carrier_id": carrier.id,
                   "route_id": route.id, "weight_kg": 10}
        res = client.post("/api/shipments", json=payload)
        assert res.status_code == 201
        assert res.json()["tracking_id"] == "ACME-0001"
        dup = client.post("/api/shipments", json=payload)
        assert dup.status_code == 409
        assert dup.json()["field"] == "tracking_id"

    def test_create_delivered_sets_delivered_at(self, client, refs):
        carrier, route = refs
        now = utcnow()
        res = client.post("/api/shipments", json={
            "customer_name": "Acme", "carrier_id": carrier.id, "route_id": route.id, "weight_kg": 10,
            "status": "delivered", "shipped_at": iso(now - timedelta(days=3)), "eta": iso(now - timedelta(days=1)),
        })
        assert res.status_code == 201
        assert res.json()["delivered_at"] is not None
        assert res.json()["is_overdue"] is False

    @pytest.mark.parametrize(
        "override, field",
        [
            ({"weight_kg": 0}, "weight_kg"),
            ({"weight_kg": -5}, "weight_kg"),
            ({"pieces": 0}, "pieces"),
            ({"customer_name": " "}, "customer_name"),
            ({"tracking_id": "bad id!"}, "tracking_id"),
            ({"status": "lost"}, "status"),
            ({"priority": "urgent"}, "priority"),
        ],
    )
    def test_field_validation(self, client, refs, override, field):
        carrier, route = refs
        payload = {"customer_name": "Acme", "carrier_id": carrier.id, "route_id": route.id, "weight_kg": 10}
        res = client.post("/api/shipments", json={**payload, **override})
        assert res.status_code == 422
        assert any(field in err["loc"] for err in res.json()["detail"])

    def test_eta_must_follow_shipped_at(self, client, refs):
        carrier, route = refs
        now = utcnow()
        res = client.post("/api/shipments", json={
            "customer_name": "Acme", "carrier_id": carrier.id, "route_id": route.id, "weight_kg": 10,
            "shipped_at": iso(now), "eta": iso(now - timedelta(hours=1)),
        })
        assert res.status_code == 422
        assert "ETA must be later" in res.text

    def test_unknown_and_inactive_references(self, client, factory, refs):
        carrier, route = refs
        base = {"customer_name": "Acme", "weight_kg": 10}
        res = client.post("/api/shipments", json={**base, "carrier_id": 999, "route_id": route.id})
        assert res.status_code == 422 and res.json()["field"] == "carrier_id"
        res = client.post("/api/shipments", json={**base, "carrier_id": carrier.id, "route_id": 999})
        assert res.status_code == 422 and res.json()["field"] == "route_id"
        inactive = factory.carrier(is_active=False)
        res = client.post("/api/shipments", json={**base, "carrier_id": inactive.id, "route_id": route.id})
        assert res.status_code == 422 and "inactive" in res.json()["detail"]


class TestReadUpdateDelete:
    def test_get_detail_and_tracking_lookup(self, client, factory):
        s = factory.shipment(tracking_id="CP26-ABCDEFGH")
        res = client.get(f"/api/shipments/{s.id}")
        assert res.status_code == 200
        assert res.json()["tracking_id"] == "CP26-ABCDEFGH"
        assert client.get("/api/shipments/tracking/cp26-abcdefgh").json()["id"] == s.id
        assert client.get("/api/shipments/99999").status_code == 404
        assert client.get("/api/shipments/tracking/NOPE-0000").status_code == 404

    def test_patch_updates_fields(self, client, factory):
        s = factory.shipment()
        new_route = factory.route()
        new_eta = utcnow() + timedelta(days=5)
        res = client.patch(f"/api/shipments/{s.id}", json={
            "customer_name": "Renamed Ltd", "priority": "critical", "route_id": new_route.id, "eta": iso(new_eta),
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["customer_name"] == "Renamed Ltd"
        assert body["priority"] == "critical"
        assert body["route"]["id"] == new_route.id

    def test_patch_validation(self, client, factory):
        s = factory.shipment()
        assert client.patch(f"/api/shipments/{s.id}", json={"status": "delivered"}).status_code == 422
        assert client.patch(f"/api/shipments/{s.id}", json={"customer_name": None}).status_code == 422
        early = iso(s.shipped_at - timedelta(days=1))
        assert client.patch(f"/api/shipments/{s.id}", json={"eta": early}).status_code == 422
        assert client.patch(f"/api/shipments/{s.id}", json={"carrier_id": 999}).status_code == 422
        assert client.patch("/api/shipments/99999", json={"customer_name": "X Y"}).status_code == 404

    def test_patch_tracking_conflict(self, client, factory):
        a = factory.shipment(tracking_id="TRACK-AAAA")
        factory.shipment(tracking_id="TRACK-BBBB")
        assert client.patch(f"/api/shipments/{a.id}", json={"tracking_id": "TRACK-BBBB"}).status_code == 409

    def test_delivered_shipment_logistics_locked(self, client, factory):
        s = factory.shipment(status="delivered")
        res = client.patch(f"/api/shipments/{s.id}", json={"eta": iso(utcnow() + timedelta(days=3))})
        assert res.status_code == 409
        assert client.patch(f"/api/shipments/{s.id}", json={"reference": "PO-1"}).status_code == 200

    def test_delete_cascades(self, client, factory, db):
        from app.models import ShipmentStatusHistory

        s = factory.shipment()
        assert client.delete(f"/api/shipments/{s.id}").status_code == 204
        assert client.get(f"/api/shipments/{s.id}").status_code == 404
        assert db.query(ShipmentStatusHistory).filter_by(shipment_id=s.id).count() == 0
        assert client.delete(f"/api/shipments/{s.id}").status_code == 404


class TestListing:
    @pytest.fixture
    def dataset(self, factory):
        now = utcnow()
        fast = factory.carrier(name="Alpha Air", code="ALA")
        slow = factory.carrier(name="Zeta Rail", code="ZTR")
        air = factory.route(mode="air", origin_city="Tokyo", destination_city="Singapore")
        rail = factory.route(mode="rail", origin_city="Hamburg", destination_city="Warsaw")
        items = {
            "a": factory.shipment(fast, air, customer_name="Harbor Foods", status="in_transit",
                                  eta=now + timedelta(days=1), tracking_id="CP26-AAAA1111"),
            "b": factory.shipment(slow, rail, customer_name="Lumen Electronics", status="delivered",
                                  eta=now - timedelta(days=1), priority="express"),
            "c": factory.shipment(slow, rail, customer_name="Harbor Foods", status="in_transit",
                                  eta=now - timedelta(hours=5), reference="PO-777"),
            "d": factory.shipment(fast, air, customer_name="Atlas Parts", status="pending",
                                  eta=now + timedelta(days=4), priority="critical"),
            "e": factory.shipment(fast, rail, customer_name="Bluebird Toys", status="cancelled",
                                  eta=now + timedelta(days=2)),
        }
        return items

    def ids(self, res):
        assert res.status_code == 200, res.text
        return [i["id"] for i in res.json()["items"]]

    def test_pagination(self, client, dataset):
        res = client.get("/api/shipments", params={"page_size": 2, "page": 1, "sort_by": "eta", "sort_order": "asc"})
        body = res.json()
        assert body["total"] == 5 and body["pages"] == 3 and len(body["items"]) == 2
        page3 = client.get("/api/shipments", params={"page_size": 2, "page": 3}).json()
        assert len(page3["items"]) == 1
        beyond = client.get("/api/shipments", params={"page_size": 2, "page": 9}).json()
        assert beyond["items"] == [] and beyond["total"] == 5

    def test_search(self, client, dataset):
        assert len(self.ids(client.get("/api/shipments", params={"search": "harbor"}))) == 2
        assert self.ids(client.get("/api/shipments", params={"search": "aaaa1111"})) == [dataset["a"].id]
        assert self.ids(client.get("/api/shipments", params={"search": "PO-777"})) == [dataset["c"].id]
        assert len(self.ids(client.get("/api/shipments", params={"search": "warsaw"}))) == 3
        assert len(self.ids(client.get("/api/shipments", params={"search": "zeta"}))) == 2
        assert self.ids(client.get("/api/shipments", params={"search": "100%_"})) == []

    def test_filters(self, client, dataset):
        d = dataset
        get = lambda **p: set(self.ids(client.get("/api/shipments", params=p)))  # noqa: E731
        assert get(status="in_transit") == {d["a"].id, d["c"].id}
        assert get(status="pending,cancelled") == {d["d"].id, d["e"].id}
        assert get(carrier_id=d["b"].carrier_id) == {d["b"].id, d["c"].id}
        assert get(route_id=d["a"].route_id) == {d["a"].id, d["d"].id}
        assert get(priority="critical") == {d["d"].id}
        assert get(mode="rail") == {d["b"].id, d["c"].id, d["e"].id}
        assert get(overdue="true") == {d["c"].id}
        assert d["c"].id not in get(overdue="false")
        eta_from = (utcnow() + timedelta(hours=12)).isoformat()
        eta_to = (utcnow() + timedelta(days=3)).isoformat()
        assert get(eta_from=eta_from, eta_to=eta_to) == {d["a"].id, d["e"].id}
        assert get(status="in_transit", search="harbor", mode="air") == {d["a"].id}

    def test_sorting(self, client, dataset):
        d = dataset
        asc = self.ids(client.get("/api/shipments", params={"sort_by": "eta", "sort_order": "asc"}))
        assert asc == [d["b"].id, d["c"].id, d["a"].id, d["e"].id, d["d"].id]
        desc = self.ids(client.get("/api/shipments", params={"sort_by": "eta", "sort_order": "desc"}))
        assert desc == list(reversed(asc))
        by_carrier = client.get("/api/shipments", params={"sort_by": "carrier", "sort_order": "asc"}).json()
        names = [i["carrier"]["name"] for i in by_carrier["items"]]
        assert names == sorted(names)
        by_customer = client.get("/api/shipments", params={"sort_by": "customer_name", "sort_order": "desc"}).json()
        customers = [i["customer_name"] for i in by_customer["items"]]
        assert customers == sorted(customers, reverse=True)

    def test_overdue_flag_in_response(self, client, dataset):
        item = client.get(f"/api/shipments/{dataset['c'].id}").json()
        assert item["is_overdue"] is True
        assert 4.5 < item["hours_overdue"] < 5.5
        assert client.get(f"/api/shipments/{dataset['b'].id}").json()["is_overdue"] is False

    @pytest.mark.parametrize(
        "params",
        [
            {"page": 0},
            {"page_size": 101},
            {"sort_by": "password"},
            {"sort_order": "sideways"},
            {"status": "teleported"},
            {"priority": "urgent"},
            {"eta_from": "2026-02-01T00:00:00Z", "eta_to": "2026-01-01T00:00:00Z"},
        ],
    )
    def test_invalid_query_params(self, client, params):
        assert client.get("/api/shipments", params=params).status_code == 422


def test_lifecycle_metadata(client):
    data = client.get("/api/shipments/lifecycle").json()
    assert data["delivered"] == [] and data["cancelled"] == []
    assert "delivered" in data["in_transit"]
    assert set(data) == {s.value for s in ShipmentStatus}
