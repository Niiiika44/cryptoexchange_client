from collections.abc import Iterable, Mapping
from decimal import Decimal
from operator import attrgetter

from price_tracker.application import Pagination, StorageUnavailableError
from price_tracker.domain import IndexPrice, Ticker, TimeRange


def make_price(
    *,
    ticker: Ticker = Ticker.BTC_USD,
    price: str = "100",
    timestamp: int = 0,
) -> IndexPrice:
    return IndexPrice(ticker=ticker, price=Decimal(price), timestamp=timestamp)


class InMemoryPriceRepository:
    """Repository over a list; ``unavailable=True`` simulates a storage outage."""

    def __init__(self, prices: Iterable[IndexPrice] = (), *, unavailable: bool = False) -> None:
        self._prices = list(prices)
        self._unavailable = unavailable

    @property
    def prices(self) -> tuple[IndexPrice, ...]:
        return tuple(self._prices)

    async def add(self, index_price: IndexPrice) -> None:
        self._ensure_available()
        if not any(
            stored.ticker == index_price.ticker and stored.timestamp == index_price.timestamp
            for stored in self._prices
        ):
            self._prices.append(index_price)

    async def get_latest(self, ticker: Ticker) -> IndexPrice | None:
        matching = self._matching(ticker, TimeRange.unbounded())
        return matching[-1] if matching else None

    async def find(
        self,
        ticker: Ticker,
        time_range: TimeRange,
        pagination: Pagination,
    ) -> list[IndexPrice]:
        matching = self._matching(ticker, time_range)
        return matching[pagination.offset : pagination.offset + pagination.limit]

    async def count(self, ticker: Ticker, time_range: TimeRange) -> int:
        return len(self._matching(ticker, time_range))

    def _matching(self, ticker: Ticker, time_range: TimeRange) -> list[IndexPrice]:
        self._ensure_available()
        return sorted(
            (
                stored
                for stored in self._prices
                if stored.ticker == ticker and time_range.contains(stored.timestamp)
            ),
            key=attrgetter("timestamp"),
        )

    def _ensure_available(self) -> None:
        if self._unavailable:
            raise StorageUnavailableError


class StubPriceProvider:
    """Answers with a preset price, or raises a preset error, per ticker."""

    def __init__(self, outcomes: Mapping[Ticker, Decimal | Exception]) -> None:
        self._outcomes = outcomes

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        outcome = self._outcomes[ticker]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FixedClock:
    def __init__(self, timestamp: int) -> None:
        self._timestamp = timestamp

    def now(self) -> int:
        return self._timestamp
