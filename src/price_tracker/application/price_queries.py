from price_tracker.application.exceptions import PriceNotFoundError
from price_tracker.application.pagination import Page, Pagination
from price_tracker.application.ports import PriceRepository
from price_tracker.domain import IndexPrice, Ticker, TimeRange


class PriceQueryService:
    """Read-side use cases over the collected index prices."""

    def __init__(self, repository: PriceRepository) -> None:
        self._repository = repository

    async def get_prices(
        self,
        ticker: Ticker,
        time_range: TimeRange,
        pagination: Pagination,
    ) -> Page[IndexPrice]:
        """Return a page of prices of ``ticker`` within ``time_range``, oldest first."""
        items = await self._repository.find(ticker, time_range, pagination)
        total = await self._repository.count(ticker, time_range)
        return Page(items=tuple(items), total=total, pagination=pagination)

    async def get_latest_price(self, ticker: Ticker) -> IndexPrice:
        """Return the most recently collected price of ``ticker``.

        Raises:
            PriceNotFoundError: Nothing has been collected for ``ticker`` yet.
        """
        index_price = await self._repository.get_latest(ticker)
        if index_price is None:
            raise PriceNotFoundError(ticker)
        return index_price
