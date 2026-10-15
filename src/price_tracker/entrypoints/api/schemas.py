from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from price_tracker.application import Page
from price_tracker.domain import IndexPrice, Ticker


class IndexPriceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: Ticker
    price: Decimal = Field(
        description="Index price in the quote currency; a string, so that it stays exact",
        examples=["81901.66"],
    )
    timestamp: int = Field(
        description="Moment of observation, UNIX timestamp in seconds",
        examples=[1791991037],
    )

    @classmethod
    def from_entity(cls, index_price: IndexPrice) -> Self:
        return cls(
            ticker=index_price.ticker,
            price=index_price.price,
            timestamp=index_price.timestamp,
        )


class IndexPricePageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[IndexPriceResponse] = Field(description="Prices ordered from oldest to newest")
    total: int = Field(description="Number of prices matching the query across all pages")
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: Page[IndexPrice]) -> Self:
        return cls(
            items=[IndexPriceResponse.from_entity(item) for item in page.items],
            total=page.total,
            limit=page.pagination.limit,
            offset=page.pagination.offset,
        )


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
