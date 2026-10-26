from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import TransportMode
from app.schemas.common import ErrorResponse, Page
from app.schemas.route import RouteCreate, RouteRead, RouteUpdate
from app.services import route_service

router = APIRouter(prefix="/routes", tags=["Routes"])

DB = Annotated[Session, Depends(get_db)]
NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}


@router.get("", response_model=Page[RouteRead], summary="List routes")
def list_routes(
    db: DB,
    search: Annotated[str | None, Query(max_length=100, description="Code, city or country")] = None,
    mode: TransportMode | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return route_service.list_routes(
        db, search=search, mode=mode, is_active=is_active, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=RouteRead,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT,
    summary="Create a route",
)
def create_route(payload: RouteCreate, db: DB):
    return route_service.create_route(db, payload)


@router.get("/{route_id}", response_model=RouteRead, responses=NOT_FOUND, summary="Get a route")
def get_route(route_id: int, db: DB):
    return route_service.get_route_read(db, route_id)


@router.patch(
    "/{route_id}",
    response_model=RouteRead,
    responses={**NOT_FOUND, **CONFLICT},
    summary="Update a route",
)
def update_route(route_id: int, payload: RouteUpdate, db: DB):
    return route_service.update_route(db, route_id, payload)


@router.delete(
    "/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, **CONFLICT},
    summary="Delete a route (only when it has no shipments)",
)
def delete_route(route_id: int, db: DB):
    route_service.delete_route(db, route_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
