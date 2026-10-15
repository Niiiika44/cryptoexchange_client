from fastapi import APIRouter

from price_tracker.entrypoints.api.schemas import HealthResponse


async def check_health() -> HealthResponse:
    return HealthResponse()


def create_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])
    router.add_api_route("/health", check_health, methods=["GET"], summary="Liveness probe")
    return router
