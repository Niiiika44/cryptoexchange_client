import asyncio
import logging

import aiohttp
from yarl import URL

from price_tracker.application import CollectIndexPrice
from price_tracker.config import Settings
from price_tracker.domain import IndexPrice, Ticker
from price_tracker.infrastructure.clock import SystemClock
from price_tracker.infrastructure.database import Database, SqlAlchemyPriceRepository
from price_tracker.infrastructure.deribit import DeribitClient


class IndexPriceCollector:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    def collect(self, ticker: Ticker) -> IndexPrice:
        index_price = asyncio.run(self._collect(ticker))
        self._logger.info(
            "Collected %s index price %s at %d",
            index_price.ticker,
            index_price.price,
            index_price.timestamp,
        )
        return index_price

    async def _collect(self, ticker: Ticker) -> IndexPrice:
        deribit_settings = self._settings.deribit
        http_timeout = aiohttp.ClientTimeout(total=deribit_settings.request_timeout_seconds)
        database = Database(self._settings.database.url)
        try:
            async with (
                asyncio.timeout(self._settings.collector.interval_seconds),
                aiohttp.ClientSession(timeout=http_timeout) as http_session,
                database.transaction() as db_session,
            ):
                use_case = CollectIndexPrice(
                    provider=DeribitClient(http_session, URL(str(deribit_settings.base_url))),
                    repository=SqlAlchemyPriceRepository(db_session),
                    clock=SystemClock(),
                )
                return await use_case.execute(ticker)
        finally:
            await database.dispose()
