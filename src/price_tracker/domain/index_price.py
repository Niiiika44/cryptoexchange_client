from dataclasses import dataclass
from decimal import Decimal

from price_tracker.domain.exceptions import InvalidPriceError, NegativeTimestampError
from price_tracker.domain.tickers import Ticker


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexPrice:
    """Index price of a currency observed at a moment in time.

    Attributes:
        ticker: Currency index the price belongs to.
        price: Index price in the quote currency.
        timestamp: Moment of observation as a UNIX timestamp in seconds.
    """

    ticker: Ticker
    price: Decimal
    timestamp: int

    def __post_init__(self) -> None:
        if not self.price.is_finite() or self.price <= 0:
            raise InvalidPriceError(self.price)
        if self.timestamp < 0:
            raise NegativeTimestampError(self.timestamp)
