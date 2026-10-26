from app.enums import ShipmentStatus


class TestCarriers:
    def test_create_and_get(self, client):
        res = client.post(
            "/api/carriers",
            json={
                "name": "  Northwind Freight ",
                "code": "nwf",
                "contact_email": "ops@northwind.example",
                "contact_phone": "+1 312 555 0101",
                "website": "https://northwind.example",
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["name"] == "Northwind Freight"
        assert body["code"] == "NWF"
        assert body["is_active"] is True
        assert body["total_shipments"] == 0
        assert body["on_time_rate"] is None

        got = client.get(f"/api/carriers/{body['id']}")
        assert got.status_code == 200
        assert got.json()["code"] == "NWF"

    def test_duplicate_code_and_name_conflict(self, client, factory):
        factory.carrier(name="BlueWave", code="BWO")
        dup_code = client.post("/api/carriers", json={"name": "Other", "code": "BWO"})
        assert dup_code.status_code == 409
        assert dup_code.json()["field"] == "code"
        dup_name = client.post("/api/carriers", json={"name": "bluewave", "code": "BW2"})
        assert dup_name.status_code == 409
        assert dup_name.json()["field"] == "name"

    def test_validation_errors(self, client):
        assert client.post("/api/carriers", json={"name": "X", "code": "OK"}).status_code == 422
        assert client.post("/api/carriers", json={"name": "Valid", "code": "TOO-LONG-CODE"}).status_code == 422
        assert (
            client.post(
                "/api/carriers", json={"name": "Valid", "code": "VAL", "contact_email": "not-an-email"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/carriers", json={"name": "Valid", "code": "VAL", "website": "ftp://x"}
            ).status_code
            == 422
        )

    def test_list_search_filter_and_stats(self, client, factory):
        a = factory.carrier(name="Alpha Air", code="ALA")
        factory.carrier(name="Beta Road", code="BTR", is_active=False)
        factory.shipment(carrier=a, status=ShipmentStatus.DELIVERED.value)
        factory.shipment(carrier=a, status=ShipmentStatus.IN_TRANSIT.value)

        res = client.get("/api/carriers", params={"search": "alpha"})
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["total_shipments"] == 2
        assert item["active_shipments"] == 1
        assert item["on_time_rate"] == 100.0

        inactive = client.get("/api/carriers", params={"is_active": False}).json()
        assert [c["code"] for c in inactive["items"]] == ["BTR"]

    def test_update_and_delete(self, client, factory):
        c = factory.carrier(name="Gamma", code="GAM")
        res = client.patch(f"/api/carriers/{c.id}", json={"is_active": False, "contact_phone": ""})
        assert res.status_code == 200
        assert res.json()["is_active"] is False
        assert res.json()["contact_phone"] is None

        assert client.delete(f"/api/carriers/{c.id}").status_code == 204
        assert client.get(f"/api/carriers/{c.id}").status_code == 404
        assert client.delete(f"/api/carriers/{c.id}").status_code == 404

    def test_cannot_delete_carrier_in_use(self, client, factory):
        s = factory.shipment()
        res = client.delete(f"/api/carriers/{s.carrier_id}")
        assert res.status_code == 409
        assert "Deactivate" in res.json()["detail"]


class TestRoutes:
    payload = {
        "origin_city": "Shanghai",
        "origin_country": "cn",
        "destination_city": "Los Angeles",
        "destination_country": "US",
        "mode": "ocean",
        "distance_km": 10460,
        "estimated_transit_days": 18,
    }

    def test_create_generates_code(self, client):
        res = client.post("/api/routes", json=self.payload)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["code"] == "SHA-LOS-OCN"
        assert body["origin_country"] == "CN"
        assert body["label"] == "Shanghai → Los Angeles"

    def test_duplicate_lane_conflict(self, client):
        assert client.post("/api/routes", json=self.payload).status_code == 201
        res = client.post("/api/routes", json={**self.payload, "origin_city": "shanghai"})
        assert res.status_code == 409
        # Same lane, different mode is a different route.
        assert client.post("/api/routes", json={**self.payload, "mode": "air"}).status_code == 201

    def test_validation(self, client):
        same = {**self.payload, "destination_city": "Shanghai", "destination_country": "CN"}
        assert client.post("/api/routes", json=same).status_code == 422
        assert client.post("/api/routes", json={**self.payload, "distance_km": 0}).status_code == 422
        assert client.post("/api/routes", json={**self.payload, "mode": "teleport"}).status_code == 422
        assert client.post("/api/routes", json={**self.payload, "origin_country": "CHN"}).status_code == 422
        assert (
            client.post("/api/routes", json={**self.payload, "estimated_transit_days": 365}).status_code
            == 422
        )

    def test_list_filter_update_delete(self, client, factory):
        air = factory.route(mode="air", origin_city="Frankfurt", destination_city="Chicago")
        factory.route(mode="rail", origin_city="Hamburg", destination_city="Warsaw")

        res = client.get("/api/routes", params={"mode": "air"}).json()
        assert [r["id"] for r in res["items"]] == [air.id]
        assert client.get("/api/routes", params={"search": "warsaw"}).json()["total"] == 1

        upd = client.patch(f"/api/routes/{air.id}", json={"estimated_transit_days": 1})
        assert upd.status_code == 200
        assert upd.json()["estimated_transit_days"] == 1
        bad = client.patch(
            f"/api/routes/{air.id}", json={"destination_city": "Frankfurt", "destination_country": "US"}
        )
        assert bad.status_code == 422

        assert client.delete(f"/api/routes/{air.id}").status_code == 204
        assert client.get(f"/api/routes/{air.id}").status_code == 404

    def test_cannot_delete_route_in_use(self, client, factory):
        s = factory.shipment()
        assert client.delete(f"/api/routes/{s.route_id}").status_code == 409
