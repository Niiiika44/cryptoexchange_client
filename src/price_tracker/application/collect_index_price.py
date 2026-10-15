from price_tracker.application.ports import Clock, IndexPriceProvider, PriceRepository
from price_tracker.domain import IndexPrice, Ticker


class CollectIndexPrice:
    """Use case: fetch the current index price of a ticker and store it."""

    def __init__(
        self,
        provider: IndexPriceProvider,
        repository: PriceRepository,
        clock: Clock,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._clock = clock

    async def execute(self, ticker: Ticker) -> IndexPrice:
        price = await self._provider.get_index_price(ticker)
        index_price = IndexPrice(ticker=ticker, price=price, timestamp=self._clock.now())
        await self._repository.add(index_price)
        return index_price
