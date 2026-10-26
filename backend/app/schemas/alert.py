from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import AlertSeverity, AlertStatus, AlertType, ShipmentStatus
from app.schemas.common import ORMModel


class AlertShipment(ORMModel):
    id: int
    tracking_id: str
    customer_name: str
    status: ShipmentStatus
    eta: datetime


class AlertRead(ORMModel):
    id: int
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    message: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None
    resolved_by: str | None
    shipment: AlertShipment


class AlertResolve(BaseModel):
    note: str | None = Field(default=None, max_length=1000, examples=["Carrier confirmed new ETA"])


class AlertCounts(BaseModel):
    active: int
    resolved: int
    by_severity: dict[str, int]


class ScanResult(BaseModel):
    scanned_at: datetime
    overdue_found: int = 0
    alerts_created: int = 0
    alerts_escalated: int = 0
    alerts_resolved: int = 0
    duplicates_skipped: int = 0
    shipments_marked_delayed: int = 0
    skipped: bool = False
    reason: str | None = None


class ScanQueued(BaseModel):
    task_id: str
    status: str


class ScanTaskStatus(BaseModel):
    task_id: str
    state: str
    result: ScanResult | None = None
    error: str | None = None


class LastScan(BaseModel):
    available: bool
    last_run: ScanResult | None = None
    interval_seconds: int
