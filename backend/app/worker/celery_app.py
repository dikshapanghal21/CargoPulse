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
    # Fail fast (instead of hanging API requests) when Redis is unreachable.
    broker_connection_timeout=3,
    redis_socket_connect_timeout=3,
    redis_socket_timeout=10,
    redis_retry_on_timeout=True,
    redis_backend_health_check_interval=10,
    result_backend_transport_options={
        "retry_policy": {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "timeout": 3}
    },
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
