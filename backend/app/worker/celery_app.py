from celery import Celery
from celery.signals import worker_ready

from app.config import settings

OVERDUE_TASK_NAME = "cargopulse.detect_overdue_shipments"

celery_app = Celery(
    "cargopulse",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="cargopulse",
    beat_schedule={
        "detect-overdue-shipments": {
            "task": OVERDUE_TASK_NAME,
            "schedule": float(settings.overdue_scan_interval_seconds),
            "options": {"expires": max(settings.overdue_scan_interval_seconds - 5, 30)},
        }
    },
)


@worker_ready.connect
def run_initial_scan(sender, **_kwargs):
    """Run one scan as soon as a worker comes up so alerts are fresh after deploys."""
    sender.app.send_task(OVERDUE_TASK_NAME)
