from unittest.mock import Mock

import pytest
from celery import Celery

from price_tracker.application import (
    ExchangeResponseError,
    ExchangeUnavailableError,
    StorageUnavailableError,
)
from price_tracker.config import CollectorSettings, Settings
from price_tracker.domain import Ticker
from price_tracker.entrypoints.worker import create_celery_app
from price_tracker.entrypoints.worker.tasks import (
    COLLECT_INDEX_PRICE_TASK,
    build_beat_schedule,
    register_collect_task,
)
from tests.fakes import make_price


@pytest.fixture
def celery_app() -> Celery:
    return Celery("test", broker="memory://")


def test_beat_schedule_collects_every_ticker_independently_at_configured_interval() -> None:
    settings = CollectorSettings(tickers=(Ticker.BTC_USD, Ticker.ETH_USD), interval_seconds=60)

    schedule = build_beat_schedule(settings)

    assert schedule == {
        "collect-btc_usd-index-price": {
            "task": COLLECT_INDEX_PRICE_TASK,
            "schedule": 60.0,
            "args": ("btc_usd",),
            "options": {"expires": 60},
        },
        "collect-eth_usd-index-price": {
            "task": COLLECT_INDEX_PRICE_TASK,
            "schedule": 60.0,
            "args": ("eth_usd",),
            "options": {"expires": 60},
        },
    }


def test_collect_task_collects_price_of_given_ticker(celery_app: Celery) -> None:
    collect = Mock(return_value=make_price(ticker=Ticker.ETH_USD))
    task = register_collect_task(celery_app, collect, CollectorSettings())

    task.apply(args=("eth_usd",)).get()

    collect.assert_called_once_with(Ticker.ETH_USD)


@pytest.mark.parametrize(
    "error",
    [ExchangeUnavailableError("Deribit"), StorageUnavailableError()],
)
def test_collect_task_retries_transient_failures(celery_app: Celery, error: Exception) -> None:
    collect = Mock(side_effect=error)
    task = register_collect_task(celery_app, collect, CollectorSettings(max_retries=2))

    result = task.apply(args=("btc_usd",))

    assert result.failed()
    assert collect.call_count == 3


def test_collect_task_does_not_retry_unusable_exchange_response(celery_app: Celery) -> None:
    collect = Mock(side_effect=ExchangeResponseError("Deribit", detail="malformed payload"))
    task = register_collect_task(celery_app, collect, CollectorSettings(max_retries=2))

    result = task.apply(args=("btc_usd",))

    assert result.failed()
    assert collect.call_count == 1


def test_celery_app_registers_collect_task_and_its_schedule(settings: Settings) -> None:
    collector_settings = CollectorSettings(tickers=(Ticker.BTC_USD,))

    app = create_celery_app(settings.model_copy(update={"collector": collector_settings}))

    assert COLLECT_INDEX_PRICE_TASK in app.tasks
    assert list(app.conf.beat_schedule) == ["collect-btc_usd-index-price"]
