"""Populate the database with realistic demo data.

Usage:
    python -m app.seed            # seed only if the database is empty
    python -m app.seed --reset    # wipe all CargoPulse data and reseed
    python -m app.seed --count 250
"""

import argparse
import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    ShipmentPriority,
    ShipmentStatus,
    TransportMode,
)
from app.models import Alert, Carrier, Route, Shipment, ShipmentStatusHistory
from app.services.alert_service import SYSTEM_ACTOR, detect_overdue_shipments, severity_for
from app.utils import utcnow

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

CARRIERS = [
    # name, code, email, phone, website, modes, active
    ("Northwind Freight", "NWF", "ops@northwindfreight.example", "+1 312 555 0141",
     "https://northwindfreight.example", {"road", "ocean"}, True),
    ("BlueWave Ocean Lines", "BWO", "bookings@bluewave.example", "+31 10 555 0199",
     "https://bluewave.example", {"ocean"}, True),
    ("SkyBridge Air Cargo", "SKY", "control@skybridge.example", "+49 69 555 0107",
     "https://skybridge.example", {"air"}, True),
    ("TransAlpine Rail", "TAR", "dispatch@transalpine.example", "+41 44 555 0112",
     "https://transalpine.example", {"rail"}, True),
    ("Meridian Express", "MEX", "support@meridianexpress.example", "+44 20 5550 0178",
     "https://meridianexpress.example", {"air", "road"}, True),
    ("Pacific Rim Logistics", "PRL", "cs@pacificrim.example", "+65 6555 0133",
     "https://pacificrim.example", {"ocean"}, True),
    ("Ironhorse Trucking", "IHT", "dispatch@ironhorse.example", "+1 214 555 0166",
     "https://ironhorse.example", {"road"}, True),
    ("Polar Star Couriers", "PSC", "hello@polarstar.example", "+47 22 55 50 10",
     None, {"air", "road"}, False),
]

ROUTES = [
    # origin, cc, destination, cc, mode, km, days
    ("Shanghai", "CN", "Los Angeles", "US", "ocean", 10460, 18),
    ("Shenzhen", "CN", "Rotterdam", "NL", "ocean", 18500, 32),
    ("Rotterdam", "NL", "New York", "US", "ocean", 6200, 12),
    ("Singapore", "SG", "Sydney", "AU", "ocean", 6300, 11),
    ("Mumbai", "IN", "Dubai", "AE", "ocean", 1930, 5),
    ("Frankfurt", "DE", "Chicago", "US", "air", 6970, 2),
    ("Hong Kong", "HK", "London", "GB", "air", 9630, 2),
    ("Tokyo", "JP", "Singapore", "SG", "air", 5320, 2),
    ("Sao Paulo", "BR", "Miami", "US", "air", 6560, 3),
    ("Chicago", "US", "Dallas", "US", "road", 1490, 3),
    ("Los Angeles", "US", "Seattle", "US", "road", 1830, 3),
    ("Toronto", "CA", "Chicago", "US", "road", 840, 2),
    ("Delhi", "IN", "Bengaluru", "IN", "road", 2150, 4),
    ("Hamburg", "DE", "Warsaw", "PL", "rail", 880, 3),
    ("Xi'an", "CN", "Duisburg", "DE", "rail", 10200, 16),
    ("Lyon", "FR", "Madrid", "ES", "rail", 1050, 2),
]

HUBS = {
    "ocean": ["Port of Busan", "Strait of Malacca", "Suez Canal transit", "Port of Colombo",
              "Mid-Pacific", "Port of Algeciras"],
    "air": ["Anchorage hub", "Dubai DWC hub", "Leipzig hub", "Doha transit", "Miami gateway"],
    "road": ["Interstate cross-dock", "Regional sort center", "Line-haul depot", "Border crossing"],
    "rail": ["Malaszewicze terminal", "Brest border yard", "Almaty railhead", "Poznan terminal"],
}

CUSTOMERS = [
    ("Harbor Lane Foods", "Refrigerated produce, 18 pallets"),
    ("Silverline Optics", "Precision lens assemblies"),
    ("Maple & Co. Furniture", "Flat-pack furniture, 2x40' containers"),
    ("Tidewater Chemicals", "Industrial solvents (non-hazmat grade)"),
    ("Crescent Pharma Distribution", "Temperature-controlled vaccines"),
    ("Lumen Electronics", "LED panel displays"),
    ("Granite Peak Outdoor", "Camping and hiking gear"),
    ("Atlas Auto Parts", "Brake assemblies and rotors"),
    ("Kestrel Medical Devices", "Surgical instrument kits"),
    ("Orchid Apparel Co.", "Seasonal apparel collection"),
    ("Summit Beverage Distributors", "Canned beverages, mixed pallets"),
    ("Redwood Paper & Pack", "Corrugated packaging rolls"),
    ("Quantum Circuits Ltd", "PCB assemblies and microcontrollers"),
    ("Bluebird Toys", "Holiday toy inventory"),
    ("Ironclad Tools", "Power tools and accessories"),
    ("Saffron Spice Traders", "Bulk spices, food-grade sacks"),
    ("Evergreen Garden Supply", "Garden equipment and planters"),
    ("Northgate Solar", "Photovoltaic modules"),
    ("Cobblestone Coffee Roasters", "Green coffee beans, 320 sacks"),
    ("Vantage Robotics Systems", "Warehouse robot components"),
]

WEIGHT_RANGES = {"air": (5, 900), "road": (250, 18000), "ocean": (1200, 24000), "rail": (2000, 22000)}


def _tracking_id(rng: random.Random, now: datetime, used: set[str]) -> str:
    while True:
        tid = f"CP{now:%y}-" + "".join(rng.choice(ALPHABET) for _ in range(8))
        if tid not in used:
            used.add(tid)
            return tid


def _lerp(start: datetime, end: datetime, fraction: float) -> datetime:
    return start + (end - start) * fraction


def reset(db: Session) -> None:
    db.execute(
        text(
            "TRUNCATE alerts, shipment_status_history, shipments, routes, carriers "
            "RESTART IDENTITY CASCADE"
        )
    )
    db.commit()


def seed(db: Session, count: int = 160, rng_seed: int = 42) -> dict:
    rng = random.Random(rng_seed)
    now = utcnow().replace(microsecond=0)

    carriers = []
    for name, code, email, phone, site, _modes, active in CARRIERS:
        c = Carrier(name=name, code=code, contact_email=email, contact_phone=phone, website=site,
                    is_active=active, created_at=now - timedelta(days=120),
                    updated_at=now - timedelta(days=rng.randint(1, 60)))
        carriers.append(c)
    db.add_all(carriers)

    routes = []
    mode_code = {"road": "RD", "rail": "RL", "air": "AIR", "ocean": "OCN"}
    for origin, occ, dest, dcc, mode, km, days in ROUTES:
        code = f"{''.join(ch for ch in origin if ch.isalnum())[:3].upper()}-" \
               f"{''.join(ch for ch in dest if ch.isalnum())[:3].upper()}-{mode_code[mode]}"
        routes.append(Route(code=code, origin_city=origin, origin_country=occ, destination_city=dest,
                            destination_country=dcc, mode=TransportMode(mode).value, distance_km=km,
                            estimated_transit_days=days, created_at=now - timedelta(days=120),
                            updated_at=now - timedelta(days=rng.randint(1, 60))))
    db.add_all(routes)
    db.flush()

    carriers_by_mode: dict[str, list[Carrier]] = {}
    for carrier, spec in zip(carriers, CARRIERS):
        if carrier.is_active:
            for mode in spec[5]:
                carriers_by_mode.setdefault(mode, []).append(carrier)

    used_ids: set[str] = set()
    shipments: list[Shipment] = []
    resolved_alerts = 0

    def add_history(s: Shipment, chain: list[tuple[str, datetime, str | None, str | None, str]]):
        prev = None
        for status, at, location, note, actor in chain:
            db.add(ShipmentStatusHistory(shipment=s, from_status=prev, to_status=status,
                                         location=location, note=note, changed_by=actor,
                                         changed_at=at))
            prev = status

    for i in range(count):
        route = rng.choice(routes)
        carrier = rng.choice(carriers_by_mode[route.mode])
        customer, description = rng.choice(CUSTOMERS)
        priority = rng.choices(
            [ShipmentPriority.STANDARD, ShipmentPriority.EXPRESS, ShipmentPriority.CRITICAL],
            weights=[70, 22, 8])[0].value
        transit = timedelta(days=route.estimated_transit_days) * rng.uniform(0.9, 1.15)
        origin = f"{route.origin_city}, {route.origin_country}"
        destination = f"{route.destination_city}, {route.destination_country}"
        hub = rng.choice(HUBS[route.mode])

        # Spread dispatch dates over the last ~55 days; a few are scheduled pickups.
        roll = rng.random()
        forced_overdue = False
        if i < 3:
            # About to breach ETA during a live demo: overdue within the next 5-30 minutes.
            eta = now + timedelta(minutes=5 + 12 * i)
            shipped_at = eta - transit
        elif i < 8:
            # Recently overdue at varying ages so alert severities are mixed.
            eta = now - timedelta(hours=[1.5, 7, 16, 30, 52][i - 3])
            shipped_at = eta - transit
            forced_overdue = True
        elif roll < 0.06:
            shipped_at = now + timedelta(hours=rng.uniform(2, 60))
            eta = shipped_at + transit
        else:
            days_ago = rng.uniform(0.2, 12) if rng.random() < 0.55 else rng.uniform(12, 55)
            shipped_at = now - timedelta(days=days_ago, hours=rng.uniform(0, 23))
            eta = shipped_at + transit
        shipped_at = shipped_at.replace(microsecond=0)
        eta = eta.replace(second=0, microsecond=0)
        created_at = min(shipped_at, now) - timedelta(hours=rng.uniform(2, 48))

        status = ShipmentStatus.PENDING.value
        delivered_at = None
        location = origin
        chain: list = [(ShipmentStatus.PENDING.value, created_at, origin, "Shipment created", "user")]
        late_delivery = False

        if shipped_at > now:
            pass  # scheduled pickup, still pending
        elif eta <= now:
            outcome = rng.random()
            hours_past_eta = (now - eta).total_seconds() / 3600
            if forced_overdue or (hours_past_eta < 96 and outcome < 0.3):
                outcome = 0.99  # still moving past its ETA
            elif outcome > 0.96:
                outcome = 0.82  # cancelled
            else:
                outcome = 0.0  # delivered
            if outcome < 0.80:
                late_delivery = rng.random() < 0.22
                if late_delivery:
                    delivered_at = eta + timedelta(hours=rng.uniform(3, 60))
                else:
                    delivered_at = eta - timedelta(hours=rng.uniform(0.5, 30))
                delivered_at = min(max(delivered_at, shipped_at + transit * 0.6), now - timedelta(minutes=30))
                delivered_at = delivered_at.replace(microsecond=0)
                if late_delivery and delivered_at <= eta:
                    late_delivery = False
                status = ShipmentStatus.DELIVERED.value
                location = destination
                chain += [
                    (ShipmentStatus.PICKED_UP.value, shipped_at, origin, "Collected from shipper", "user"),
                    (ShipmentStatus.IN_TRANSIT.value, _lerp(shipped_at, delivered_at, 0.15), hub,
                     "Departed origin facility", "user"),
                ]
                if late_delivery:
                    chain.append((ShipmentStatus.DELAYED.value, eta + timedelta(minutes=5), hub,
                                  f"ETA passed ({eta:%Y-%m-%d %H:%M} UTC); automatically flagged as delayed",
                                  SYSTEM_ACTOR))
                else:
                    chain.append((ShipmentStatus.OUT_FOR_DELIVERY.value,
                                  _lerp(shipped_at, delivered_at, 0.93), destination,
                                  "With local delivery partner", "user"))
                chain.append((ShipmentStatus.DELIVERED.value, delivered_at, destination,
                              "Delivered, signed by consignee", "user"))
            elif outcome < 0.85:
                status = ShipmentStatus.CANCELLED.value
                cancel_at = _lerp(created_at, shipped_at, 0.8)
                chain.append((status, cancel_at, origin, "Cancelled at customer request", "user"))
            else:
                # Still moving past its ETA -> the overdue monitor will flag it.
                status = rng.choice([ShipmentStatus.IN_TRANSIT.value, ShipmentStatus.OUT_FOR_DELIVERY.value])
                location = hub if status == ShipmentStatus.IN_TRANSIT.value else destination
                chain += [
                    (ShipmentStatus.PICKED_UP.value, shipped_at, origin, "Collected from shipper", "user"),
                    (ShipmentStatus.IN_TRANSIT.value, _lerp(shipped_at, eta, 0.15), hub,
                     "Departed origin facility", "user"),
                ]
                if status == ShipmentStatus.OUT_FOR_DELIVERY.value:
                    chain.append((status, _lerp(shipped_at, eta, 0.95), destination,
                                  "With local delivery partner", "user"))
        else:
            progress = (now - shipped_at) / (eta - shipped_at)
            if rng.random() < 0.03:
                status = ShipmentStatus.CANCELLED.value
                chain.append((status, _lerp(created_at, now, 0.7), origin, "Cancelled by shipper", "user"))
            elif progress < 0.04:
                status = ShipmentStatus.PENDING.value
            else:
                chain.append((ShipmentStatus.PICKED_UP.value, shipped_at, origin, "Collected from shipper", "user"))
                status = ShipmentStatus.PICKED_UP.value
                if progress >= 0.12:
                    status = ShipmentStatus.IN_TRANSIT.value
                    location = hub
                    chain.append((status, _lerp(shipped_at, now, 0.25), hub, "Departed origin facility", "user"))
                if progress >= 0.9:
                    status = ShipmentStatus.OUT_FOR_DELIVERY.value
                    location = destination
                    chain.append((status, _lerp(shipped_at, now, 0.97), destination,
                                  "With local delivery partner", "user"))

        weight_lo, weight_hi = WEIGHT_RANGES[route.mode]
        shipment = Shipment(
            tracking_id=_tracking_id(rng, now, used_ids),
            reference=f"PO-{rng.randint(10000, 99999)}" if rng.random() < 0.85 else None,
            customer_name=customer,
            description=description,
            carrier_id=carrier.id,
            route_id=route.id,
            status=status,
            priority=priority,
            weight_kg=Decimal(str(round(rng.uniform(weight_lo, weight_hi), 2))),
            pieces=rng.randint(1, 40),
            current_location=location,
            shipped_at=shipped_at,
            eta=eta,
            delivered_at=delivered_at,
            created_at=created_at,
            updated_at=chain[-1][1],
        )
        db.add(shipment)
        db.flush()
        add_history(shipment, chain)

        if late_delivery:
            hours_late = (delivered_at - eta).total_seconds() / 3600
            sev = severity_for(hours_late, priority)
            db.add(Alert(
                shipment_id=shipment.id,
                alert_type=AlertType.OVERDUE.value,
                severity=sev.value if sev != AlertSeverity.LOW else AlertSeverity.MEDIUM.value,
                status=AlertStatus.RESOLVED.value,
                message=(f"Shipment {shipment.tracking_id} for {customer} missed its ETA of "
                         f"{eta:%Y-%m-%d %H:%M} UTC on {route.origin_city} → {route.destination_city} "
                         f"({carrier.name})."),
                dedupe_key=f"overdue:{shipment.id}:{int(eta.timestamp())}",
                created_at=eta + timedelta(minutes=5),
                updated_at=delivered_at,
                resolved_at=delivered_at,
                resolution_note="Auto-resolved: shipment delivered",
                resolved_by=SYSTEM_ACTOR,
            ))
            resolved_alerts += 1
        shipments.append(shipment)

    db.commit()
    scan = detect_overdue_shipments(db, now=now)
    return {
        "carriers": len(carriers),
        "routes": len(routes),
        "shipments": len(shipments),
        "historical_alerts": resolved_alerts,
        "active_alerts_created": scan.alerts_created,
        "marked_delayed": scan.shipments_marked_delayed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CargoPulse demo data")
    parser.add_argument("--reset", action="store_true", help="Delete existing data first")
    parser.add_argument("--count", type=int, default=160, help="Number of shipments")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset(db)
            print("Existing data removed.")
        elif db.execute(select(func.count(Shipment.id))).scalar_one() > 0:
            print("Database already contains shipments; skipping seed (use --reset to reseed).")
            return
        elif db.execute(select(func.count(Carrier.id))).scalar_one() > 0:
            print("Database already contains carriers; skipping seed (use --reset to reseed).")
            return
        summary = seed(db, count=args.count)
    print("Seed complete: " + ", ".join(f"{k}={v}" for k, v in summary.items()))


if __name__ == "__main__":
    main()
