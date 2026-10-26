from datetime import datetime

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.enums import TransportMode
from app.schemas.common import ORMModel


class _RouteFields(BaseModel):
    @field_validator("origin_country", "destination_country", "code", mode="before", check_fields=False)
    @classmethod
    def upper(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()
            return value or None
        return value

    @field_validator("origin_city", "destination_city", mode="before", check_fields=False)
    @classmethod
    def strip_city(cls, value):
        return value.strip() if isinstance(value, str) else value


class RouteCreate(_RouteFields):
    code: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9-]{3,20}$",
        description="Optional lane code. Generated from origin/destination/mode when omitted.",
        examples=["SHA-LAX-OCN"],
    )
    origin_city: str = Field(min_length=2, max_length=100, examples=["Shanghai"])
    origin_country: str = Field(pattern=r"^[A-Z]{2}$", examples=["CN"])
    destination_city: str = Field(min_length=2, max_length=100, examples=["Los Angeles"])
    destination_country: str = Field(pattern=r"^[A-Z]{2}$", examples=["US"])
    mode: TransportMode
    distance_km: int = Field(gt=0, le=40000)
    estimated_transit_days: int = Field(gt=0, le=120)
    is_active: bool = True

    @model_validator(mode="after")
    def check_lane(self):
        if (
            self.origin_city.lower() == self.destination_city.lower()
            and self.origin_country == self.destination_country
        ):
            raise ValueError("Origin and destination must be different")
        return self


class RouteUpdate(_RouteFields):
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9-]{3,20}$")
    origin_city: str | None = Field(default=None, min_length=2, max_length=100)
    origin_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    destination_city: str | None = Field(default=None, min_length=2, max_length=100)
    destination_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    mode: TransportMode | None = None
    distance_km: int | None = Field(default=None, gt=0, le=40000)
    estimated_transit_days: int | None = Field(default=None, gt=0, le=120)
    is_active: bool | None = None


class RouteSummary(ORMModel):
    id: int
    code: str
    origin_city: str
    origin_country: str
    destination_city: str
    destination_country: str
    mode: TransportMode

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.origin_city} → {self.destination_city}"


class RouteRead(RouteSummary):
    distance_km: int
    estimated_transit_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    total_shipments: int = 0
    active_shipments: int = 0
