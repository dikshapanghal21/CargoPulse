from fastapi import APIRouter

from app.api.endpoints import alerts, carriers, dashboard, health, routes, shipments

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(shipments.router)
api_router.include_router(carriers.router)
api_router.include_router(routes.router)
api_router.include_router(alerts.router)
