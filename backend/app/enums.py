from enum import StrEnum


class ShipmentStatus(StrEnum):
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


ACTIVE_STATUSES: frozenset[ShipmentStatus] = frozenset(
    {
        ShipmentStatus.PENDING,
        ShipmentStatus.PICKED_UP,
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.DELAYED,
    }
)
TERMINAL_STATUSES: frozenset[ShipmentStatus] = frozenset(
    {ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED}
)
# Statuses counted as "in transit" on the dashboard (goods physically moving).
IN_TRANSIT_STATUSES: frozenset[ShipmentStatus] = frozenset(
    {ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY}
)

# Allowed lifecycle transitions: current status -> set of permitted next statuses.
STATUS_TRANSITIONS: dict[ShipmentStatus, frozenset[ShipmentStatus]] = {
    ShipmentStatus.PENDING: frozenset(
        {ShipmentStatus.PICKED_UP, ShipmentStatus.DELAYED, ShipmentStatus.CANCELLED}
    ),
    ShipmentStatus.PICKED_UP: frozenset(
        {ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED, ShipmentStatus.CANCELLED}
    ),
    ShipmentStatus.IN_TRANSIT: frozenset(
        {
            ShipmentStatus.OUT_FOR_DELIVERY,
            ShipmentStatus.DELIVERED,
            ShipmentStatus.DELAYED,
            ShipmentStatus.CANCELLED,
        }
    ),
    ShipmentStatus.OUT_FOR_DELIVERY: frozenset(
        {ShipmentStatus.DELIVERED, ShipmentStatus.DELAYED, ShipmentStatus.IN_TRANSIT}
    ),
    ShipmentStatus.DELAYED: frozenset(
        {
            ShipmentStatus.PICKED_UP,
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.OUT_FOR_DELIVERY,
            ShipmentStatus.DELIVERED,
            ShipmentStatus.CANCELLED,
        }
    ),
    ShipmentStatus.DELIVERED: frozenset(),
    ShipmentStatus.CANCELLED: frozenset(),
}


class ShipmentPriority(StrEnum):
    STANDARD = "standard"
    EXPRESS = "express"
    CRITICAL = "critical"


class TransportMode(StrEnum):
    ROAD = "road"
    RAIL = "rail"
    AIR = "air"
    OCEAN = "ocean"


class AlertType(StrEnum):
    OVERDUE = "overdue"


class AlertSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_RANK: dict[AlertSeverity, int] = {
    AlertSeverity.LOW: 1,
    AlertSeverity.MEDIUM: 2,
    AlertSeverity.HIGH: 3,
    AlertSeverity.CRITICAL: 4,
}


class AlertStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


def sql_in(values) -> str:
    """Render enum values as a SQL IN list for CHECK constraints."""
    return ", ".join(f"'{v.value}'" for v in values)


def values(items) -> list[str]:
    """Plain string values (sorted) for use in SQL IN clauses."""
    return sorted(i.value for i in items)
