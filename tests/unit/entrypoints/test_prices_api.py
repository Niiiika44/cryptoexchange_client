from collections.abc import AsyncIterator

import httpx2
import pytest

from price_tracker.application import PriceQueryService, PriceRepository
from price_tracker.config import Settings
from price_tracker.domain import Ticker
from price_tracker.entrypoints.api import create_app
from price_tracker.entrypoints.api.dependencies import (
    MAX_OFFSET,
    MAX_PAGE_SIZE,
    get_price_query_service,
)
from tests.fakes import InMemoryPriceRepository, make_price

PRICE_ENDPOINTS = ("/api/v1/prices", "/api/v1/prices/latest", "/api/v1/prices/by-date")


@pytest.fixture
def repository() -> InMemoryPriceRepository:
    return InMemoryPriceRepository(
        [
            make_price(price="100.5", timestamp=1_791_990_000),
            make_price(price="101.25", timestamp=1_791_990_060),
            make_price(price="102", timestamp=1_791_990_120),
            make_price(ticker=Ticker.ETH_USD, price="5", timestamp=1_791_990_000),
        ],
    )


@pytest.fixture
async def api(
    settings: Settings,
    repository: PriceRepository,
) -> AsyncIterator[httpx2.AsyncClient]:
    app = create_app(settings)
    app.dependency_overrides[get_price_query_service] = lambda: PriceQueryService(repository)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_get_prices_returns_all_prices_of_ticker_oldest_first(
    api: httpx2.AsyncClient,
) -> None:
    response = await api.get("/api/v1/prices", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"ticker": "btc_usd", "price": "100.5", "timestamp": 1_791_990_000},
            {"ticker": "btc_usd", "price": "101.25", "timestamp": 1_791_990_060},
            {"ticker": "btc_usd", "price": "102", "timestamp": 1_791_990_120},
        ],
        "total": 3,
        "limit": 100,
        "offset": 0,
    }


async def test_get_prices_returns_requested_page(api: httpx2.AsyncClient) -> None:
    response = await api.get(
        "/api/v1/prices",
        params={"ticker": "btc_usd", "limit": 1, "offset": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["timestamp"] for item in body["items"]] == [1_791_990_120]
    assert (body["total"], body["limit"], body["offset"]) == (3, 1, 2)


@pytest.mark.parametrize("limit", [0, MAX_PAGE_SIZE + 1])
async def test_get_prices_rejects_page_size_out_of_bounds(
    api: httpx2.AsyncClient,
    limit: int,
) -> None:
    response = await api.get("/api/v1/prices", params={"ticker": "btc_usd", "limit": limit})

    assert response.status_code == 422


@pytest.mark.parametrize("offset", [-1, MAX_OFFSET + 1])
async def test_get_prices_rejects_offset_out_of_bounds(
    api: httpx2.AsyncClient, offset: int
) -> None:
    response = await api.get("/api/v1/prices", params={"ticker": "btc_usd", "offset": offset})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "offset"]


async def test_get_prices_accepts_largest_offset_storage_can_handle(
    api: httpx2.AsyncClient,
) -> None:
    response = await api.get("/api/v1/prices", params={"ticker": "btc_usd", "offset": MAX_OFFSET})

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_get_latest_price_returns_most_recent_price(api: httpx2.AsyncClient) -> None:
    response = await api.get("/api/v1/prices/latest", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == {"ticker": "btc_usd", "price": "102", "timestamp": 1_791_990_120}


@pytest.mark.parametrize("repository", [InMemoryPriceRepository()])
async def test_get_latest_price_returns_404_when_nothing_collected(
    api: httpx2.AsyncClient,
) -> None:
    response = await api.get("/api/v1/prices/latest", params={"ticker": "eth_usd"})

    assert response.status_code == 404
    assert response.json() == {"detail": "No index prices have been collected for eth_usd yet"}


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [
        ("2026-10-14T15:01:00Z", "2026-10-14T15:02:00Z"),
        ("2026-10-14T18:01:00+03:00", "2026-10-14T18:02:00+03:00"),
        ("1791990060", "1791990120"),
    ],
)
async def test_get_prices_by_date_returns_prices_within_inclusive_bounds(
    api: httpx2.AsyncClient,
    date_from: str,
    date_to: str,
) -> None:
    response = await api.get(
        "/api/v1/prices/by-date",
        params={"ticker": "btc_usd", "date_from": date_from, "date_to": date_to},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["timestamp"] for item in body["items"]] == [1_791_990_060, 1_791_990_120]
    assert body["total"] == 2


async def test_get_prices_by_date_accepts_open_ended_range(api: httpx2.AsyncClient) -> None:
    response = await api.get(
        "/api/v1/prices/by-date",
        params={"ticker": "btc_usd", "date_to": "1791990060"},
    )

    assert response.status_code == 200
    assert [item["timestamp"] for item in response.json()["items"]] == [
        1_791_990_000,
        1_791_990_060,
    ]


async def test_get_prices_by_date_rejects_range_ending_before_it_starts(
    api: httpx2.AsyncClient,
) -> None:
    response = await api.get(
        "/api/v1/prices/by-date",
        params={"ticker": "btc_usd", "date_from": "1791990120", "date_to": "1791990060"},
    )

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["loc"] == ["query", "date_to"]
    assert "must not be after" in error["msg"]


async def test_get_prices_by_date_rejects_datetime_without_timezone(
    api: httpx2.AsyncClient,
) -> None:
    response = await api.get(
        "/api/v1/prices/by-date",
        params={"ticker": "btc_usd", "date_from": "2026-10-14T15:01:00"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", PRICE_ENDPOINTS)
async def test_price_endpoints_require_ticker(api: httpx2.AsyncClient, endpoint: str) -> None:
    response = await api.get(endpoint)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "ticker"]


@pytest.mark.parametrize("endpoint", PRICE_ENDPOINTS)
async def test_price_endpoints_reject_unknown_ticker(
    api: httpx2.AsyncClient,
    endpoint: str,
) -> None:
    response = await api.get(endpoint, params={"ticker": "doge_usd"})

    assert response.status_code == 422


@pytest.mark.parametrize("repository", [InMemoryPriceRepository(unavailable=True)])
@pytest.mark.parametrize("endpoint", PRICE_ENDPOINTS)
async def test_price_endpoints_report_unavailable_storage_as_503(
    api: httpx2.AsyncClient,
    endpoint: str,
) -> None:
    response = await api.get(endpoint, params={"ticker": "btc_usd"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Price storage is temporarily unavailable"}


async def test_health_reports_ok(api: httpx2.AsyncClient) -> None:
    response = await api.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
