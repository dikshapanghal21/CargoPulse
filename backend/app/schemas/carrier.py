from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel, blank_to_none

PHONE_PATTERN = r"^\+?[0-9 ()\-]{6,40}$"
URL_PATTERN = r"^https?://[^\s]+$"


class _CarrierFields(BaseModel):
    @field_validator("code", mode="before", check_fields=False)
    @classmethod
    def upper_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("contact_email", "contact_phone", "website", mode="before", check_fields=False)
    @classmethod
    def empty_optional(cls, value):
        value = blank_to_none(value)
        return value.strip() if isinstance(value, str) else value


class CarrierCreate(_CarrierFields):
    name: str = Field(min_length=2, max_length=120, examples=["Northwind Freight"])
    code: str = Field(pattern=r"^[A-Z0-9]{2,10}$", examples=["NWF"])
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    website: str | None = Field(default=None, max_length=255, pattern=URL_PATTERN)
    is_active: bool = True


class CarrierUpdate(_CarrierFields):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9]{2,10}$")
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    website: str | None = Field(default=None, max_length=255, pattern=URL_PATTERN)
    is_active: bool | None = None


class CarrierSummary(ORMModel):
    id: int
    name: str
    code: str


class CarrierRead(ORMModel):
    id: int
    name: str
    code: str
    contact_email: str | None
    contact_phone: str | None
    website: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    total_shipments: int = 0
    active_shipments: int = 0
    delayed_shipments: int = 0
    on_time_rate: float | None = None
