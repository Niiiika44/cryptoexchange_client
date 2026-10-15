import asyncio
import gzip
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from http import HTTPStatus

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from yarl import URL

from price_tracker.application import ExchangeResponseError, ExchangeUnavailableError
from price_tracker.domain import Ticker
from price_tracker.infrastructure.deribit import DeribitClient

INDEX_PRICE_BODY = {
    "jsonrpc": "2.0",
    "result": {"index_price": 81901.66, "estimated_delivery_price": 81901.66},
    "usIn": 1791991037989280,
    "usOut": 1791991037989672,
    "usDiff": 392,
    "testnet": False,
}
INVALID_PARAMS_BODY = {
    "jsonrpc": "2.0",
    "error": {"code": -32602, "message": "Invalid params"},
    "testnet": False,
}


class FakeDeribit:
    """Real HTTP server standing in for Deribit."""

    def __init__(self) -> None:
        self.status = HTTPStatus.OK
        self.body = json.dumps(INDEX_PRICE_BODY).encode()
        self.headers: dict[str, str] = {}
        self.delay_seconds = 0.0
        self.received_queries: list[dict[str, str]] = []

    async def handle(self, request: web.Request) -> web.Response:
        self.received_queries.append(dict(request.query))
        await asyncio.sleep(self.delay_seconds)
        return web.Response(
            status=self.status,
            body=self.body,
            headers=self.headers,
            content_type="application/json",
        )

    async def handle_valid_price(self, _: web.Request) -> web.Response:
        return web.json_response(INDEX_PRICE_BODY)


@pytest.fixture
def deribit() -> FakeDeribit:
    return FakeDeribit()


@pytest.fixture
async def deribit_url(deribit: FakeDeribit) -> AsyncIterator[URL]:
    app = web.Application()
    app.router.add_get("/api/v2/public/get_index_price", deribit.handle)
    app.router.add_get("/elsewhere", deribit.handle_valid_price)
    async with TestServer(app) as server:
        yield server.make_url("/api/v2")


@pytest.fixture
async def client(deribit_url: URL) -> AsyncIterator[DeribitClient]:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=0.5)) as session:
        yield DeribitClient(session, deribit_url)


async def test_get_index_price_returns_exact_decimal(client: DeribitClient) -> None:
    assert await client.get_index_price(Ticker.BTC_USD) == Decimal("81901.66")


@pytest.mark.parametrize("ticker", list(Ticker))
async def test_get_index_price_requests_index_named_after_ticker(
    client: DeribitClient,
    deribit: FakeDeribit,
    ticker: Ticker,
) -> None:
    await client.get_index_price(ticker)

    assert deribit.received_queries == [{"index_name": ticker.value}]


@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
    ],
)
async def test_get_index_price_reports_overload_and_server_errors_as_unavailable(
    client: DeribitClient,
    deribit: FakeDeribit,
    status: HTTPStatus,
) -> None:
    deribit.status = status

    with pytest.raises(ExchangeUnavailableError):
        await client.get_index_price(Ticker.BTC_USD)


async def test_get_index_price_reports_timeout_as_unavailable(
    client: DeribitClient,
    deribit: FakeDeribit,
) -> None:
    deribit.delay_seconds = 1.0

    with pytest.raises(ExchangeUnavailableError):
        await client.get_index_price(Ticker.BTC_USD)


async def test_get_index_price_reports_connection_failure_as_unavailable() -> None:
    async with aiohttp.ClientSession() as session:
        client = DeribitClient(session, URL("http://127.0.0.1:1/api/v2"))

        with pytest.raises(ExchangeUnavailableError):
            await client.get_index_price(Ticker.BTC_USD)


async def test_get_index_price_reports_json_rpc_error_with_its_details(
    client: DeribitClient,
    deribit: FakeDeribit,
) -> None:
    deribit.status = HTTPStatus.BAD_REQUEST
    deribit.body = json.dumps(INVALID_PARAMS_BODY).encode()

    with pytest.raises(ExchangeResponseError, match="-32602: Invalid params"):
        await client.get_index_price(Ticker.BTC_USD)


@pytest.mark.parametrize(
    "body",
    [
        b"<html>Bad gateway</html>",
        json.dumps({"jsonrpc": "2.0", "result": {"estimated_delivery_price": 1}}).encode(),
        json.dumps({"jsonrpc": "2.0", "result": {"index_price": 0}}).encode(),
        json.dumps({"jsonrpc": "2.0"}).encode(),
    ],
)
async def test_get_index_price_reports_unusable_payload(
    client: DeribitClient,
    deribit: FakeDeribit,
    body: bytes,
) -> None:
    deribit.body = body

    with pytest.raises(ExchangeResponseError):
        await client.get_index_price(Ticker.BTC_USD)


async def test_get_index_price_does_not_follow_redirects(
    client: DeribitClient,
    deribit: FakeDeribit,
) -> None:
    deribit.status = HTTPStatus.FOUND
    deribit.headers = {"Location": "/elsewhere"}

    with pytest.raises(ExchangeResponseError, match="unexpected redirect"):
        await client.get_index_price(Ticker.BTC_USD)


async def test_get_index_price_refuses_oversized_response(
    client: DeribitClient,
    deribit: FakeDeribit,
) -> None:
    deribit.body = json.dumps({**INDEX_PRICE_BODY, "padding": "x" * 100_000}).encode()

    with pytest.raises(ExchangeResponseError, match="too large"):
        await client.get_index_price(Ticker.BTC_USD)


async def test_get_index_price_limits_decompressed_size_of_response(
    client: DeribitClient,
    deribit: FakeDeribit,
) -> None:
    deribit.body = gzip.compress(b'{"padding": "' + b"0" * 10_000_000 + b'"}')
    deribit.headers = {"Content-Encoding": "gzip"}

    with pytest.raises(ExchangeResponseError, match="too large"):
        await client.get_index_price(Ticker.BTC_USD)
