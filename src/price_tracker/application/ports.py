from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from price_tracker.application.pagination import Pagination
from price_tracker.domain import IndexPrice, Ticker, TimeRange


class IndexPriceProvider(Protocol):
    """Source of current currency index prices, e.g. a crypto exchange."""

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        """Return the current index price of ``ticker``.

        Raises:
            ExchangeUnavailableError: The source failed transiently; retrying may help.
            ExchangeResponseError: The source answered with an error or an unusable payload.
        """


class PriceRepository(Protocol):
    """Persistent collection of observed index prices.

    Every method raises ``StorageUnavailableError`` when the storage cannot be reached.
    """

    async def add(self, index_price: IndexPrice) -> None:
        """Store an observation; a duplicate of an already stored one is ignored."""

    async def get_latest(self, ticker: Ticker) -> IndexPrice | None:
        """Return the most recent observation of ``ticker``, if there is any."""

    async def find(
        self,
        ticker: Ticker,
        time_range: TimeRange,
        pagination: Pagination,
    ) -> Sequence[IndexPrice]:
        """Return observations of ``ticker`` within ``time_range``, oldest first."""

    async def count(self, ticker: Ticker, time_range: TimeRange) -> int:
        """Return how many observations of ``ticker`` fall within ``time_range``."""


class Clock(Protocol):
    def now(self) -> int:
        """Return the current UNIX timestamp in seconds."""
