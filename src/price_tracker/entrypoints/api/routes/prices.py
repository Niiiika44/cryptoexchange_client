from http import HTTPStatus

from fastapi import APIRouter

from price_tracker.domain import TimeRange
from price_tracker.entrypoints.api.dependencies import (
    PaginationDep,
    PriceQueryServiceDep,
    TickerQuery,
    TimeRangeDep,
)
from price_tracker.entrypoints.api.schemas import (
    ErrorResponse,
    IndexPricePageResponse,
    IndexPriceResponse,
)


async def get_prices(
    ticker: TickerQuery,
    pagination: PaginationDep,
    service: PriceQueryServiceDep,
) -> IndexPricePageResponse:
    page = await service.get_prices(ticker, TimeRange.unbounded(), pagination)
    return IndexPricePageResponse.from_page(page)


async def get_latest_price(
    ticker: TickerQuery,
    service: PriceQueryServiceDep,
) -> IndexPriceResponse:
    index_price = await service.get_latest_price(ticker)
    return IndexPriceResponse.from_entity(index_price)


async def get_prices_by_date(
    ticker: TickerQuery,
    time_range: TimeRangeDep,
    pagination: PaginationDep,
    service: PriceQueryServiceDep,
) -> IndexPricePageResponse:
    page = await service.get_prices(ticker, time_range, pagination)
    return IndexPricePageResponse.from_page(page)


def create_prices_router() -> APIRouter:
    router = APIRouter(
        prefix="/prices",
        tags=["prices"],
        responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
    )
    router.add_api_route(
        "",
        get_prices,
        methods=["GET"],
        summary="All prices of a ticker",
    )
    router.add_api_route(
        "/latest",
        get_latest_price,
        methods=["GET"],
        summary="Latest price of a ticker",
        responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
    )
    router.add_api_route(
        "/by-date",
        get_prices_by_date,
        methods=["GET"],
        summary="Prices of a ticker filtered by date",
    )
    return router
