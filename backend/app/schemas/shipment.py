from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.enums import ACTIVE_STATUSES, AlertSeverity, AlertStatus, AlertType, ShipmentPriority, ShipmentStatus
from app.schemas.carrier import CarrierSummary
from app.schemas.common import AwareDatetime, ORMModel, blank_to_none
from app.schemas.route import RouteSummary
from app.utils import utcnow

TRACKING_PATTERN = r"^[A-Z0-9-]{6,32}$"


class _ShipmentFields(BaseModel):
    @field_validator("tracking_id", mode="before", check_fields=False)
    @classmethod
    def normalise_tracking(cls, value):
        value = blank_to_none(value)
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator(
        "reference", "description", "current_location", mode="before", check_fields=False
    )
    @classmethod
    def empty_optional(cls, value):
        value = blank_to_none(value)
        return value.strip() if isinstance(value, str) else value

    @field_validator("customer_name", mode="before", check_fields=False)
    @classmethod
    def strip_customer(cls, value):
        return value.strip() if isinstance(value, str) else value


class ShipmentCreate(_ShipmentFields):
    tracking_id: str | None = Field(
        default=None,
        pattern=TRACKING_PATTERN,
        description="Optional custom tracking ID; generated (e.g. CP26-7K3M9QX2) when omitted.",
    )
    reference: str | None = Field(default=None, max_length=64, examples=["PO-48213"])
    customer_name: str = Field(min_length=2, max_length=160, examples=["Acme Industrial Supply"])
    description: str | None = Field(default=None, max_length=2000)
    carrier_id: int = Field(gt=0)
    route_id: int = Field(gt=0)
    status: ShipmentStatus = ShipmentStatus.PENDING
    priority: ShipmentPriority = ShipmentPriority.STANDARD
    weight_kg: Decimal = Field(gt=0, le=1_000_000, max_digits=10, decimal_places=2)
    pieces: int = Field(default=1, ge=1, le=100_000)
    current_location: str | None = Field(default=None, max_length=160)
    shipped_at: AwareDatetime | None = Field(
        default=None, description="Pickup/dispatch time. Defaults to now."
    )
    eta: AwareDatetime | None = Field(
        default=None,
        description="Estimated arrival. Defaults to shipped_at + the route's transit days.",
    )
    delivered_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.shipped_at and self.eta and self.eta <= self.shipped_at:
            raise ValueError("ETA must be later than the shipped date")
        if self.delivered_at and self.status != ShipmentStatus.DELIVERED:
            raise ValueError("delivered_at can only be set when status is 'delivered'")
        if self.delivered_at and self.shipped_at and self.delivered_at < self.shipped_at:
            raise ValueError("delivered_at cannot be earlier than the shipped date")
        if self.delivered_at and self.delivered_at > utcnow():
            raise ValueError("delivered_at cannot be in the future")
        return self


class ShipmentUpdate(_ShipmentFields):
    """Partial update. Status changes go through POST /shipments/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    tracking_id: str | None = Field(default=None, pattern=TRACKING_PATTERN)
    reference: str | None = Field(default=None, max_length=64)
    customer_name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    carrier_id: int | None = Field(default=None, gt=0)
    route_id: int | None = Field(default=None, gt=0)
    priority: ShipmentPriority | None = None
    weight_kg: Decimal | None = Field(default=None, gt=0, le=1_000_000, max_digits=10, decimal_places=2)
    pieces: int | None = Field(default=None, ge=1, le=100_000)
    current_location: str | None = Field(default=None, max_length=160)
    shipped_at: AwareDatetime | None = None
    eta: AwareDatetime | None = None


class StatusUpdate(BaseModel):
    status: ShipmentStatus
    note: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=160)
    eta: AwareDatetime | None = Field(default=None, description="Optionally revise the ETA.")
    delivered_at: AwareDatetime | None = Field(
        default=None, description="Delivery time when status is 'delivered'. Defaults to now."
    )

    @field_validator("note", "location", mode="before")
    @classmethod
    def empty_optional(cls, value):
        value = blank_to_none(value)
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def check_delivered(self):
        if self.delivered_at and self.status != ShipmentStatus.DELIVERED:
            raise ValueError("delivered_at can only be set when status is 'delivered'")
        if self.delivered_at and self.delivered_at > utcnow():
            raise ValueError("delivered_at cannot be in the future")
        return self


class StatusHistoryRead(ORMModel):
    id: int
    from_status: ShipmentStatus | None
    to_status: ShipmentStatus
    location: str | None
    note: str | None
    changed_by: str
    changed_at: datetime


class AlertBrief(ORMModel):
    id: int
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    message: str
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None
    resolved_by: str | None


class ShipmentRead(ORMModel):
    id: int
    tracking_id: str
    reference: str | None
    customer_name: str
    description: str | None
    carrier: CarrierSummary
    route: RouteSummary
    status: ShipmentStatus
    priority: ShipmentPriority
    weight_kg: float
    pieces: int
    current_location: str | None
    shipped_at: datetime
    eta: datetime
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return self.status in ACTIVE_STATUSES and self.eta < utcnow()

    @computed_field
    @property
    def hours_overdue(self) -> float | None:
        if not self.is_overdue:
            return None
        return round((utcnow() - self.eta).total_seconds() / 3600, 1)


class ShipmentDetail(ShipmentRead):
    status_history: list[StatusHistoryRead]
    alerts: list[AlertBrief]
    allowed_transitions: list[ShipmentStatus] = []
