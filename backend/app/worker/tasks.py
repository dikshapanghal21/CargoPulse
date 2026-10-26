import json
import logging

from redis.exceptions import LockError, RedisError

from app.config import settings
from app.database import SessionLocal
from app.redis_client import get_redis
from app.schemas.alert import ScanResult
from app.services.alert_service import detect_overdue_shipments
from app.services.dashboard_service import LAST_SCAN_KEY
from app.utils import utcnow
from app.worker.celery_app import OVERDUE_TASK_NAME, celery_app

logger = logging.getLogger(__name__)

SCAN_LOCK_KEY = "cargopulse:locks:overdue-scan"


def run_overdue_scan() -> dict:
    """Run one overdue scan guarded by a Redis lock so overlapping runs never race.

    Returns the scan summary as a JSON-serialisable dict.
    """
    redis = get_redis()
    lock = redis.lock(SCAN_LOCK_KEY, timeout=settings.overdue_lock_timeout_seconds, blocking=False)
    if not lock.acquire(blocking=False):
        logger.info("Overdue scan skipped: another scan holds the lock")
        return ScanResult(
            scanned_at=utcnow(), skipped=True, reason="Another scan is already running"
        ).model_dump(mode="json")

    try:
        with SessionLocal() as db:
            result = detect_overdue_shipments(db, grace_minutes=settings.overdue_grace_minutes)
        payload = result.model_dump(mode="json")
        try:
            redis.set(LAST_SCAN_KEY, json.dumps(payload))
        except RedisError as exc:  # pragma: no cover - status cache is best effort
            logger.warning("Could not store last scan summary: %s", exc)
        logger.info(
            "Overdue scan: %s overdue, %s created, %s escalated, %s resolved, %s duplicates skipped",
            result.overdue_found,
            result.alerts_created,
            result.alerts_escalated,
            result.alerts_resolved,
            result.duplicates_skipped,
        )
        return payload
    finally:
        try:
            lock.release()
        except LockError:  # lock expired while we were working
            logger.warning("Overdue scan lock expired before release")


@celery_app.task(
    name=OVERDUE_TASK_NAME,
    autoretry_for=(RedisError,),
    retry_backoff=True,
    max_retries=3,
)
def detect_overdue_shipments_task() -> dict:
    return run_overdue_scan()
