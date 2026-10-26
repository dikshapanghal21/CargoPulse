from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.database import get_db
from app.redis_client import get_redis

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness and dependency check")
def health(db: Annotated[Session, Depends(get_db)]):
    checks = {"database": "ok", "redis": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - exercised only when DB is down
        checks["database"] = f"error: {exc.__class__.__name__}"
    try:
        get_redis().ping()
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"
    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "version": __version__, "checks": checks},
    )
