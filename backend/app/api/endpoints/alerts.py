import logging
from typing import Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import AlertSeverity, AlertStatus
from app.exceptions import ServiceUnavailableError
from app.schemas.alert import (
    AlertCounts,
    AlertRead,
    AlertResolve,
    LastScan,
    ScanQueued,
    ScanResult,
    ScanTaskStatus,
)
from app.schemas.common import ErrorResponse, Page
from app.services import alert_service, dashboard_service
from app.worker.celery_app import celery_app
from app.worker.tasks import detect_overdue_shipments_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])

DB = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[AlertRead], summary="List alerts (active first, by severity)")
def list_alerts(
    db: DB,
    status_filter: Annotated[AlertStatus | None, Query(alias="status")] = None,
    severity: AlertSeverity | None = None,
    shipment_id: Annotated[int | None, Query(gt=0)] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return alert_service.list_alerts(
        db,
        status=status_filter,
        severity=severity,
        shipment_id=shipment_id,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/counts", response_model=AlertCounts, summary="Alert counts by status and severity")
def counts(db: DB):
    return alert_service.alert_counts(db)


@router.post(
    "/scan",
    response_model=ScanQueued,
    status_code=status.HTTP_202_ACCEPTED,
    responses={503: {"model": ErrorResponse}},
    summary="Queue an overdue-shipment scan on the Celery worker",
)
def queue_scan():
    try:
        task = detect_overdue_shipments_task.apply_async(retry=False)
    except Exception as exc:
        logger.exception("Could not queue overdue scan")
        raise ServiceUnavailableError(
            "Task queue unavailable: cannot reach Redis. Check that Redis and the Celery worker are running."
        ) from exc
    return ScanQueued(task_id=task.id, status="queued")


@router.get("/scan/last", response_model=LastScan, summary="Result of the most recent scan")
def last_scan():
    result = dashboard_service.get_last_scan()
    return LastScan(
        available=result is not None,
        last_run=result,
        interval_seconds=settings.overdue_scan_interval_seconds,
    )


@router.get("/scan/{task_id}", response_model=ScanTaskStatus, summary="Status of a queued scan")
def scan_status(task_id: str):
    try:
        res = AsyncResult(task_id, app=celery_app)
        state = res.state
        payload = ScanTaskStatus(task_id=task_id, state=state)
        if state == "SUCCESS":
            payload.result = ScanResult.model_validate(res.result)
        elif state == "FAILURE":
            payload.error = str(res.result)
    except Exception as exc:
        raise ServiceUnavailableError(f"Result backend unavailable: {exc}") from exc
    return payload


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertRead,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Resolve an alert",
)
def resolve(alert_id: int, payload: AlertResolve, db: DB):
    return alert_service.resolve_alert_by_id(db, alert_id, payload.note)
