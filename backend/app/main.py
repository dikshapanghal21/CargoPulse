import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.config import settings
from app.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DESCRIPTION = """
**CargoPulse** — logistics & shipment intelligence API.

* **Shipments** — CRUD, search, filtering, sorting, pagination and a validated lifecycle
  with persistent status history.
* **Carriers & Routes** — master data management.
* **Alerts** — overdue shipments are detected by a scheduled Celery task (Redis broker)
  with database-enforced de-duplication and automatic resolution.
* **Dashboard** — live metrics computed from PostgreSQL.
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.app_name, "version": __version__, "docs": "/docs"}

    return app


app = create_app()
