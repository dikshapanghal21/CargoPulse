from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.carrier import CarrierCreate, CarrierRead, CarrierUpdate
from app.schemas.common import ErrorResponse, Page
from app.services import carrier_service

router = APIRouter(prefix="/carriers", tags=["Carriers"])

DB = Annotated[Session, Depends(get_db)]
NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}


@router.get("", response_model=Page[CarrierRead], summary="List carriers")
def list_carriers(
    db: DB,
    search: Annotated[str | None, Query(max_length=100, description="Name, code or email")] = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return carrier_service.list_carriers(
        db, search=search, is_active=is_active, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=CarrierRead,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT,
    summary="Create a carrier",
)
def create_carrier(payload: CarrierCreate, db: DB):
    return carrier_service.create_carrier(db, payload)


@router.get("/{carrier_id}", response_model=CarrierRead, responses=NOT_FOUND, summary="Get a carrier")
def get_carrier(carrier_id: int, db: DB):
    return carrier_service.get_carrier_read(db, carrier_id)


@router.patch(
    "/{carrier_id}",
    response_model=CarrierRead,
    responses={**NOT_FOUND, **CONFLICT},
    summary="Update a carrier",
)
def update_carrier(carrier_id: int, payload: CarrierUpdate, db: DB):
    return carrier_service.update_carrier(db, carrier_id, payload)


@router.delete(
    "/{carrier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, **CONFLICT},
    summary="Delete a carrier (only when it has no shipments)",
)
def delete_carrier(carrier_id: int, db: DB):
    carrier_service.delete_carrier(db, carrier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
