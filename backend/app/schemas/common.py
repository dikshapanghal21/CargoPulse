from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.utils import ensure_aware

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorResponse(BaseModel):
    detail: str
    code: str
    field: str | None = None


class MessageResponse(BaseModel):
    message: str


AwareDatetime = Annotated[datetime, AfterValidator(ensure_aware)]
TrimmedStr = Annotated[str, StringConstraints(strip_whitespace=True)]


def blank_to_none(value):
    if isinstance(value, str) and not value.strip():
        return None
    return value
