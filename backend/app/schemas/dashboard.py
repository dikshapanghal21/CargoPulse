from datetime import date

from pydantic import BaseModel

from app.schemas.alert import AlertRead, ScanResult
from app.schemas.shipment import ShipmentRead


class DashboardSummary(BaseModel):
    total_shipments: int
    in_transit: int
    delivered: int
    delayed: int
    pending: int
    cancelled: int
    overdue: int
    active_alerts: int
    critical_alerts: int
    on_time_rate: float | None
    due_next_7_days: int


class StatusCount(BaseModel):
    status: str
    count: int


class VolumePoint(BaseModel):
    date: date
    shipped: int
    delivered: int


class CarrierPerformance(BaseModel):
    carrier_id: int
    carrier: str
    code: str
    total: int
    active: int
    delivered: int
    delayed: int
    on_time_rate: float | None


class ModeCount(BaseModel):
    mode: str
    count: int
    active: int = 0
    delayed: int = 0
    on_time_rate: float | None = None


class DashboardData(BaseModel):
    summary: DashboardSummary
    status_breakdown: list[StatusCount]
    volume_trend: list[VolumePoint]
    carrier_performance: list[CarrierPerformance]
    mode_breakdown: list[ModeCount]
    recent_shipments: list[ShipmentRead]
    upcoming_deliveries: list[ShipmentRead]
    active_alerts: list[AlertRead]
    last_scan: ScanResult | None = None
