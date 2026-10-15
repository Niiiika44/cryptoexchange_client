import pytest

from price_tracker.application import Pagination, PriceNotFoundError, PriceQueryService
from price_tracker.domain import Ticker, TimeRange
from tests.fakes import InMemoryPriceRepository, make_price

BTC_HISTORY = (
    make_price(price="100", timestamp=60),
    make_price(price="101", timestamp=120),
    make_price(price="102", timestamp=180),
)
ETH_PRICE = make_price(ticker=Ticker.ETH_USD, price="5", timestamp=240)


@pytest.fixture
def service() -> PriceQueryService:
    return PriceQueryService(InMemoryPriceRepository([BTC_HISTORY[2], ETH_PRICE, *BTC_HISTORY[:2]]))


async def test_get_prices_returns_all_prices_of_ticker_oldest_first(
    service: PriceQueryService,
) -> None:
    page = await service.get_prices(Ticker.BTC_USD, TimeRange.unbounded(), Pagination(limit=10))

    assert page.items == BTC_HISTORY
    assert page.total == 3


async def test_get_prices_returns_requested_window_and_full_total(
    service: PriceQueryService,
) -> None:
    pagination = Pagination(limit=1, offset=1)

    page = await service.get_prices(Ticker.BTC_USD, TimeRange.unbounded(), pagination)

    assert page.items == (BTC_HISTORY[1],)
    assert page.total == 3
    assert page.pagination == pagination


async def test_get_prices_filters_by_time_range(service: PriceQueryService) -> None:
    page = await service.get_prices(
        Ticker.BTC_USD,
        TimeRange(start=120, end=180),
        Pagination(limit=10),
    )

    assert page.items == BTC_HISTORY[1:]
    assert page.total == 2


async def test_get_latest_price_returns_most_recent_price_of_ticker(
    service: PriceQueryService,
) -> None:
    assert await service.get_latest_price(Ticker.BTC_USD) == BTC_HISTORY[-1]


async def test_get_latest_price_raises_when_nothing_collected() -> None:
    service = PriceQueryService(InMemoryPriceRepository())

    with pytest.raises(PriceNotFoundError):
        await service.get_latest_price(Ticker.BTC_USD)
