"""Request-scoped wiring of the API: query parsing and use case construction."""

import math
from collections.abc import AsyncIterator
from typing import Annotated, Final

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from price_tracker.application import Pagination, PriceQueryService
from price_tracker.domain import InvalidTimeRangeError, Ticker, TimeRange
from price_tracker.infrastructure.database import Database, SqlAlchemyPriceRepository

DEFAULT_PAGE_SIZE: Final = 100
MAX_PAGE_SIZE: Final = 1000
MAX_OFFSET: Final = 2**63 - 1


def get_database(request: Request) -> Database:
    database: Database = request.state.database
    return database


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.read_only_session() as session:
        yield session


def get_price_query_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PriceQueryService:
    return PriceQueryService(SqlAlchemyPriceRepository(session))


def get_pagination(
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of prices to return"),
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[
        int,
        Query(ge=0, le=MAX_OFFSET, description="Number of prices to skip"),
    ] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


def get_time_range(
    date_from: Annotated[
        AwareDatetime | None,
        Query(
            description="Inclusive lower bound: ISO 8601 with a timezone or a UNIX timestamp",
            examples=["2026-10-14T00:00:00Z"],
        ),
    ] = None,
    date_to: Annotated[
        AwareDatetime | None,
        Query(
            description="Inclusive upper bound: ISO 8601 with a timezone or a UNIX timestamp",
            examples=["1791991037"],
        ),
    ] = None,
) -> TimeRange:
    start = None if date_from is None else math.floor(date_from.timestamp())
    end = None if date_to is None else math.floor(date_to.timestamp())
    try:
        return TimeRange(start=start, end=end)
    except InvalidTimeRangeError as error:
        # Reported like any other invalid query parameter, in FastAPI's 422 format.
        detail = {"type": "value_error", "loc": ("query", "date_to"), "msg": str(error)}
        raise RequestValidationError([{**detail, "input": date_to}]) from error


TickerQuery = Annotated[Ticker, Query(description="Currency index to query")]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]
TimeRangeDep = Annotated[TimeRange, Depends(get_time_range)]
PriceQueryServiceDep = Annotated[PriceQueryService, Depends(get_price_query_service)]
