import math
import secrets
from datetime import UTC, datetime

_TRACKING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_aware(value: datetime | None) -> datetime | None:
    """Treat naive datetimes as UTC so comparisons are always timezone-safe."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def generate_tracking_id(now: datetime | None = None) -> str:
    now = now or utcnow()
    suffix = "".join(secrets.choice(_TRACKING_ALPHABET) for _ in range(8))
    return f"CP{now:%y}-{suffix}"


def page_count(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size)) if page_size else 1
