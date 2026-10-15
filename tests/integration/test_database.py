from collections.abc import AsyncIterator

import pytest
from sqlalchemy import URL, delete
from sqlalchemy.exc import DBAPIError

from price_tracker.application import Pagination
from price_tracker.domain import Ticker, TimeRange
from price_tracker.entrypoints.api.dependencies import MAX_OFFSET
from price_tracker.infrastructure.database import (
    Database,
    IndexPriceRecord,
    SqlAlchemyPriceRepository,
)
from tests.fakes import make_price

pytestmark = pytest.mark.integration


@pytest.fixture
async def database(database_url: URL) -> AsyncIterator[Database]:
    database = Database(database_url)
    yield database
    async with database.transaction() as session:
        await session.execute(delete(IndexPriceRecord))
    await database.dispose()


async def test_read_only_session_rejects_writes(database: Database) -> None:
    async with database.read_only_session() as session:
        with pytest.raises(DBAPIError, match="read-only transaction"):
            await SqlAlchemyPriceRepository(session).add(make_price())


async def test_read_only_session_reads_a_single_snapshot(database: Database) -> None:
    async with database.read_only_session() as reader:
        repository = SqlAlchemyPriceRepository(reader)
        assert await repository.count(Ticker.BTC_USD, TimeRange.unbounded()) == 0

        async with database.transaction() as writer:
            await SqlAlchemyPriceRepository(writer).add(make_price())

        assert await repository.count(Ticker.BTC_USD, TimeRange.unbounded()) == 0
        assert await repository.get_latest(Ticker.BTC_USD) is None


async def test_largest_accepted_offset_is_valid_for_postgresql(database: Database) -> None:
    async with database.read_only_session() as session:
        found = await SqlAlchemyPriceRepository(session).find(
            Ticker.BTC_USD,
            TimeRange.unbounded(),
            Pagination(limit=1, offset=MAX_OFFSET),
        )

    assert found == []
