import pytest
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from price_tracker.application import StorageUnavailableError
from price_tracker.domain import Ticker
from price_tracker.infrastructure.database import SqlAlchemyPriceRepository
from price_tracker.infrastructure.database.errors import translate_connectivity_errors


def _dbapi_error(*, connection_invalidated: bool) -> exc.DBAPIError:
    return exc.DBAPIError(
        statement="SELECT 1",
        params=None,
        orig=Exception("driver error"),
        connection_invalidated=connection_invalidated,
    )


@pytest.mark.parametrize(
    "error",
    [
        ConnectionRefusedError(),
        TimeoutError(),
        exc.TimeoutError(),
        exc.OperationalError("SELECT 1", None, Exception("server closed the connection")),
        _dbapi_error(connection_invalidated=True),
    ],
)
def test_connectivity_failures_become_storage_unavailable(error: Exception) -> None:
    with pytest.raises(StorageUnavailableError), translate_connectivity_errors():
        raise error


@pytest.mark.parametrize(
    "error",
    [
        _dbapi_error(connection_invalidated=False),
        exc.IntegrityError("INSERT", None, Exception("duplicate key")),
        ValueError("not a database problem"),
    ],
)
def test_other_failures_propagate_unchanged(error: Exception) -> None:
    with pytest.raises(type(error)), translate_connectivity_errors():
        raise error


async def test_repository_reports_unreachable_database_as_storage_unavailable() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:secret@127.0.0.1:1/db")
    try:
        async with AsyncSession(engine) as session:
            repository = SqlAlchemyPriceRepository(session)

            with pytest.raises(StorageUnavailableError):
                await repository.get_latest(Ticker.BTC_USD)
    finally:
        await engine.dispose()
