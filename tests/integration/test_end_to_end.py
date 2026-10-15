import asyncio
import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from pydantic import HttpUrl
from sqlalchemy import URL, NullPool, delete
from sqlalchemy.ext.asyncio import create_async_engine

from price_tracker.config import CollectorSettings, DatabaseSettings, DeribitSettings, Settings
from price_tracker.domain import Ticker
from price_tracker.entrypoints.api import create_app
from price_tracker.entrypoints.worker.collector import IndexPriceCollector
from price_tracker.infrastructure.database import IndexPriceRecord

pytestmark = pytest.mark.integration

INDEX_PRICE_BODY = json.dumps(
    {"jsonrpc": "2.0", "result": {"index_price": 81901.66, "estimated_delivery_price": 81901.66}},
).encode()


class FakeDeribitServer(ThreadingHTTPServer):
    """Deribit stand-in that answers every request with a valid index price."""

    block_on_close = False

    def __init__(self, *, delay_seconds: float = 0.0) -> None:
        super().__init__(("127.0.0.1", 0), FakeDeribitHandler)
        self.delay_seconds = delay_seconds

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/api/v2"

    def handle_error(self, request: object, client_address: object) -> None:
        """A client that gave up on a slow answer is expected here."""


class FakeDeribitHandler(BaseHTTPRequestHandler):
    server: FakeDeribitServer

    def do_GET(self) -> None:
        time.sleep(self.server.delay_seconds)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(INDEX_PRICE_BODY)))
        self.end_headers()
        self.wfile.write(INDEX_PRICE_BODY)

    def log_message(self, *_: object) -> None:
        """Keep the test output clean."""


@contextmanager
def serve_fake_deribit(*, delay_seconds: float = 0.0) -> Iterator[FakeDeribitServer]:
    server = FakeDeribitServer(delay_seconds=delay_seconds)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def deribit_url() -> Iterator[str]:
    with serve_fake_deribit() as server:
        yield server.base_url


@pytest.fixture
def settings(database_url: URL, deribit_url: str) -> Iterator[Settings]:
    yield Settings(
        database=DatabaseSettings().model_copy(update={"db": database_url.database}),
        deribit=DeribitSettings(base_url=HttpUrl(deribit_url)),
    )
    asyncio.run(_delete_collected_prices(database_url))


def test_collected_price_is_served_by_api(settings: Settings) -> None:
    collected = IndexPriceCollector(settings).collect(Ticker.BTC_USD)

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/prices/latest", params={"ticker": "btc_usd"})

    assert collected.price == Decimal("81901.66")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "ticker": "btc_usd",
        "price": "81901.66",
        "timestamp": collected.timestamp,
    }


def test_collection_run_never_outlives_collection_interval(settings: Settings) -> None:
    interval_seconds = 1
    with serve_fake_deribit(delay_seconds=10) as hanging_deribit:
        collector = IndexPriceCollector(
            settings.model_copy(
                update={
                    "deribit": DeribitSettings(
                        base_url=HttpUrl(hanging_deribit.base_url),
                        request_timeout_seconds=30,
                    ),
                    "collector": CollectorSettings(interval_seconds=interval_seconds),
                },
            ),
        )
        started = time.monotonic()

        with pytest.raises(TimeoutError):
            collector.collect(Ticker.BTC_USD)

    assert time.monotonic() - started < interval_seconds + 1


async def _delete_collected_prices(url: URL) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(delete(IndexPriceRecord))
    finally:
        await engine.dispose()
