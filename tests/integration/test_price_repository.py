from decimal import Decimal

import pytest

from price_tracker.application import Pagination
from price_tracker.domain import Ticker, TimeRange
from price_tracker.infrastructure.database import SqlAlchemyPriceRepository
from tests.fakes import make_price

pytestmark = pytest.mark.integration

BTC_HISTORY = (
    make_price(price="81901.66", timestamp=60),
    make_price(price="81910.1", timestamp=120),
    make_price(price="81899.999", timestamp=180),
)
ETH_PRICE = make_price(ticker=Ticker.ETH_USD, price="2500.5", timestamp=240)
EVERYTHING = Pagination(limit=100)


@pytest.fixture
async def filled_repository(repository: SqlAlchemyPriceRepository) -> SqlAlchemyPriceRepository:
    for index_price in (BTC_HISTORY[2], ETH_PRICE, *BTC_HISTORY[:2]):
        await repository.add(index_price)
    return repository


async def test_add_keeps_price_exactly_as_observed(repository: SqlAlchemyPriceRepository) -> None:
    await repository.add(make_price(price="81901.66", timestamp=60))

    stored = await repository.get_latest(Ticker.BTC_USD)

    assert stored is not None
    assert str(stored.price) == "81901.66"


async def test_add_ignores_second_observation_of_ticker_in_same_second(
    repository: SqlAlchemyPriceRepository,
) -> None:
    await repository.add(make_price(price="100", timestamp=60))
    await repository.add(make_price(price="200", timestamp=60))

    stored = await repository.find(Ticker.BTC_USD, TimeRange.unbounded(), EVERYTHING)

    assert [index_price.price for index_price in stored] == [Decimal(100)]


async def test_get_latest_returns_most_recent_price_of_ticker(
    filled_repository: SqlAlchemyPriceRepository,
) -> None:
    assert await filled_repository.get_latest(Ticker.BTC_USD) == BTC_HISTORY[-1]


async def test_get_latest_returns_none_when_nothing_stored(
    repository: SqlAlchemyPriceRepository,
) -> None:
    assert await repository.get_latest(Ticker.BTC_USD) is None


async def test_find_returns_prices_of_ticker_oldest_first(
    filled_repository: SqlAlchemyPriceRepository,
) -> None:
    found = await filled_repository.find(Ticker.BTC_USD, TimeRange.unbounded(), EVERYTHING)

    assert tuple(found) == BTC_HISTORY


@pytest.mark.parametrize(
    ("time_range", "expected_timestamps"),
    [
        (TimeRange(start=120, end=180), [120, 180]),
        (TimeRange(start=61, end=179), [120]),
        (TimeRange(start=120), [120, 180]),
        (TimeRange(end=120), [60, 120]),
        (TimeRange(start=181), []),
    ],
)
async def test_find_and_count_respect_inclusive_time_range(
    filled_repository: SqlAlchemyPriceRepository,
    time_range: TimeRange,
    expected_timestamps: list[int],
) -> None:
    found = await filled_repository.find(Ticker.BTC_USD, time_range, EVERYTHING)
    total = await filled_repository.count(Ticker.BTC_USD, time_range)

    assert [index_price.timestamp for index_price in found] == expected_timestamps
    assert total == len(expected_timestamps)


async def test_find_returns_requested_window(
    filled_repository: SqlAlchemyPriceRepository,
) -> None:
    found = await filled_repository.find(
        Ticker.BTC_USD,
        TimeRange.unbounded(),
        Pagination(limit=1, offset=1),
    )

    assert tuple(found) == (BTC_HISTORY[1],)
