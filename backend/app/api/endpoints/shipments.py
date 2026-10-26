from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import STATUS_TRANSITIONS, ShipmentPriority, ShipmentStatus, TransportMode
from app.exceptions import BusinessValidationError
from app.schemas.common import ErrorResponse, Page
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentDetail,
    ShipmentRead,
    ShipmentUpdate,
    StatusHistoryRead,
    StatusUpdate,
)
from app.services import shipment_service
from app.services.shipment_service import ShipmentFilters, ShipmentSortField, SortOrder

router = APIRouter(prefix="/shipments", tags=["Shipments"])

DB = Annotated[Session, Depends(get_db)]
NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}
INVALID = {422: {"description": "Validation error"}}


def parse_statuses(raw: str | None) -> list[ShipmentStatus] | None:
    if not raw:
        return None
    statuses = []
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        try:
            statuses.append(ShipmentStatus(part))
        except ValueError:
            allowed = ", ".join(s.value for s in ShipmentStatus)
            raise BusinessValidationError(
                f"Unknown status '{part}'. Allowed: {allowed}", field="status"
            ) from None
    return statuses or None


@router.get("/lifecycle", summary="Shipment statuses and allowed transitions")
def lifecycle() -> dict[str, list[str]]:
    return {
        s.value: [t.value for t in ShipmentStatus if t in STATUS_TRANSITIONS[s]]
        for s in ShipmentStatus
    }


@router.get("", response_model=Page[ShipmentRead], summary="Search, filter, sort and paginate shipments")
def list_shipments(
    db: DB,
    search: Annotated[
        str | None,
        Query(max_length=100, description="Tracking ID, customer, reference, city, lane or carrier"),
    ] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="One or more statuses, comma-separated"),
    ] = None,
    carrier_id: Annotated[int | None, Query(gt=0)] = None,
    route_id: Annotated[int | None, Query(gt=0)] = None,
    priority: ShipmentPriority | None = None,
    mode: TransportMode | None = None,
    overdue: Annotated[bool | None, Query(description="Only (or exclude) overdue shipments")] = None,
    eta_from: datetime | None = None,
    eta_to: datetime | None = None,
    sort_by: ShipmentSortField = ShipmentSortField.CREATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    if eta_from and eta_to and eta_from > eta_to:
        raise BusinessValidationError("eta_from must be before eta_to", field="eta_from")
    filters = ShipmentFilters(
        search=search,
        statuses=parse_statuses(status_filter),
        carrier_id=carrier_id,
        route_id=route_id,
        priority=priority,
        mode=mode,
        overdue=overdue,
        eta_from=eta_from,
        eta_to=eta_to,
    )
    return shipment_service.list_shipments(
        db, filters, sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=ShipmentDetail,
    status_code=status.HTTP_201_CREATED,
    responses={**CONFLICT, **INVALID},
    summary="Create a shipment",
)
def create_shipment(payload: ShipmentCreate, db: DB):
    return shipment_service.create_shipment(db, payload)


@router.get(
    "/tracking/{tracking_id}",
    response_model=ShipmentDetail,
    responses=NOT_FOUND,
    summary="Look up a shipment by tracking ID",
)
def get_by_tracking(tracking_id: str, db: DB):
    return shipment_service.get_shipment_by_tracking(db, tracking_id)


@router.get(
    "/{shipment_id}", response_model=ShipmentDetail, responses=NOT_FOUND, summary="Get shipment detail"
)
def get_shipment(shipment_id: int, db: DB):
    return shipment_service.get_shipment_detail(db, shipment_id)


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentDetail,
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
    summary="Update shipment details (not status)",
)
def update_shipment(shipment_id: int, payload: ShipmentUpdate, db: DB):
    return shipment_service.update_shipment(db, shipment_id, payload)


@router.delete(
    "/{shipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Delete a shipment and its history",
)
def delete_shipment(shipment_id: int, db: DB):
    shipment_service.delete_shipment(db, shipment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{shipment_id}/status",
    response_model=ShipmentDetail,
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
    summary="Advance the shipment lifecycle",
    description="Validates the transition, records it in the status history, and resolves "
    "alerts that no longer apply.",
)
def change_status(shipment_id: int, payload: StatusUpdate, db: DB):
    return shipment_service.change_status(db, shipment_id, payload)


@router.get(
    "/{shipment_id}/history",
    response_model=list[StatusHistoryRead],
    responses=NOT_FOUND,
    summary="Status history (newest first)",
)
def get_history(shipment_id: int, db: DB):
    return shipment_service.get_shipment_detail(db, shipment_id).status_history
