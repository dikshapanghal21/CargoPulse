from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import (
    CarrierPerformance,
    DashboardData,
    DashboardSummary,
    StatusCount,
    VolumePoint,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DB = Annotated[Session, Depends(get_db)]


@router.get("", response_model=DashboardData, summary="Everything the dashboard needs in one call")
def dashboard(db: DB, trend_days: Annotated[int, Query(ge=7, le=180)] = 30):
    return dashboard_service.get_dashboard(db, trend_days)


@router.get("/summary", response_model=DashboardSummary, summary="Headline shipment metrics")
def summary(db: DB):
    return dashboard_service.get_summary(db)


@router.get("/status-breakdown", response_model=list[StatusCount])
def status_breakdown(db: DB):
    return dashboard_service.get_status_breakdown(db)


@router.get("/volume-trend", response_model=list[VolumePoint])
def volume_trend(db: DB, days: Annotated[int, Query(ge=7, le=180)] = 30):
    return dashboard_service.get_volume_trend(db, days)


@router.get("/carrier-performance", response_model=list[CarrierPerformance])
def carrier_performance(db: DB):
    return dashboard_service.get_carrier_performance(db)
