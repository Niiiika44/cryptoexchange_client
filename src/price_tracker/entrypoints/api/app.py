from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import TypedDict

from fastapi import FastAPI

from price_tracker.config import Settings
from price_tracker.entrypoints.api.errors import register_error_handlers
from price_tracker.entrypoints.api.routes.health import create_health_router
from price_tracker.entrypoints.api.routes.prices import create_prices_router
from price_tracker.infrastructure.database import Database


class _LifespanState(TypedDict):
    database: Database


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[_LifespanState]:
        database = Database(app_settings.database.url)
        try:
            yield {"database": database}
        finally:
            await database.dispose()

    app = FastAPI(
        title="Crypto Index Prices",
        summary="Index prices of cryptocurrencies collected from Deribit every minute.",
        version=version("price-tracker"),
        lifespan=lifespan,
    )
    app.include_router(create_prices_router(), prefix="/api/v1")
    app.include_router(create_health_router())
    register_error_handlers(app)
    return app
