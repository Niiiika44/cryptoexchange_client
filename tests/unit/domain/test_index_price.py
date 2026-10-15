from decimal import Decimal

import pytest

from price_tracker.domain import IndexPrice, InvalidPriceError, NegativeTimestampError, Ticker


def test_index_price_keeps_observed_values() -> None:
    index_price = IndexPrice(
        ticker=Ticker.ETH_USD, price=Decimal("2500.25"), timestamp=1_700_000_000
    )

    assert index_price.ticker is Ticker.ETH_USD
    assert index_price.price == Decimal("2500.25")
    assert index_price.timestamp == 1_700_000_000


@pytest.mark.parametrize("price", ["0", "-0.01", "NaN", "sNaN", "Infinity", "-Infinity"])
def test_index_price_rejects_price_that_is_not_positive_finite_number(price: str) -> None:
    with pytest.raises(InvalidPriceError):
        IndexPrice(ticker=Ticker.BTC_USD, price=Decimal(price), timestamp=0)


def test_index_price_rejects_negative_timestamp() -> None:
    with pytest.raises(NegativeTimestampError):
        IndexPrice(ticker=Ticker.BTC_USD, price=Decimal(1), timestamp=-1)
