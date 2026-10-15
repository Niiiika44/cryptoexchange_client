from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from price_tracker.application import Pagination
from price_tracker.domain import IndexPrice, Ticker, TimeRange
from price_tracker.infrastructure.database.errors import translate_connectivity_errors
from price_tracker.infrastructure.database.models import IndexPriceRecord


class SqlAlchemyPriceRepository:
    """``PriceRepository`` backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, index_price: IndexPrice) -> None:
        statement = (
            insert(IndexPriceRecord)
            .values(
                ticker=index_price.ticker.value,
                price=index_price.price,
                timestamp=index_price.timestamp,
            )
            .on_conflict_do_nothing(
                index_elements=[IndexPriceRecord.ticker, IndexPriceRecord.timestamp],
            )
        )
        with translate_connectivity_errors():
            await self._session.execute(statement)

    async def get_latest(self, ticker: Ticker) -> IndexPrice | None:
        statement = (
            select(IndexPriceRecord)
            .where(IndexPriceRecord.ticker == ticker.value)
            .order_by(IndexPriceRecord.timestamp.desc())
            .limit(1)
        )
        with translate_connectivity_errors():
            record = await self._session.scalar(statement)
        return None if record is None else record.to_entity()

    async def find(
        self,
        ticker: Ticker,
        time_range: TimeRange,
        pagination: Pagination,
    ) -> list[IndexPrice]:
        statement = (
            select(IndexPriceRecord)
            .where(*self._matching(ticker, time_range))
            .order_by(IndexPriceRecord.timestamp)
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        with translate_connectivity_errors():
            records = (await self._session.scalars(statement)).all()
        return [record.to_entity() for record in records]

    async def count(self, ticker: Ticker, time_range: TimeRange) -> int:
        statement = (
            select(func.count())
            .select_from(IndexPriceRecord)
            .where(*self._matching(ticker, time_range))
        )
        with translate_connectivity_errors():
            result = await self._session.execute(statement)
        return result.scalar_one()

    @staticmethod
    def _matching(ticker: Ticker, time_range: TimeRange) -> list[ColumnElement[bool]]:
        conditions = [IndexPriceRecord.ticker == ticker.value]
        if time_range.start is not None:
            conditions.append(IndexPriceRecord.timestamp >= time_range.start)
        if time_range.end is not None:
            conditions.append(IndexPriceRecord.timestamp <= time_range.end)
        return conditions
