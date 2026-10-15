from decimal import Decimal

import pytest

from price_tracker.application import CollectIndexPrice, ExchangeUnavailableError
from price_tracker.domain import IndexPrice, Ticker
from tests.fakes import FixedClock, InMemoryPriceRepository, StubPriceProvider


async def test_collect_stores_current_price_with_current_timestamp() -> None:
    repository = InMemoryPriceRepository()
    use_case = CollectIndexPrice(
        provider=StubPriceProvider({Ticker.BTC_USD: Decimal("81901.66")}),
        repository=repository,
        clock=FixedClock(1_791_991_037),
    )

    collected = await use_case.execute(Ticker.BTC_USD)

    expected = IndexPrice(ticker=Ticker.BTC_USD, price=Decimal("81901.66"), timestamp=1_791_991_037)
    assert collected == expected
    assert repository.prices == (expected,)


async def test_collect_stores_nothing_when_exchange_fails() -> None:
    repository = InMemoryPriceRepository()
    use_case = CollectIndexPrice(
        provider=StubPriceProvider({Ticker.BTC_USD: ExchangeUnavailableError("Deribit")}),
        repository=repository,
        clock=FixedClock(0),
    )

    with pytest.raises(ExchangeUnavailableError):
        await use_case.execute(Ticker.BTC_USD)

    assert repository.prices == ()
