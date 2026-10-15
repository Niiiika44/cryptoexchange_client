from collections.abc import Callable
from typing import Any, Final

from celery import Celery, Task

from price_tracker.application import ExchangeUnavailableError, StorageUnavailableError
from price_tracker.config import CollectorSettings
from price_tracker.domain import IndexPrice, Ticker

COLLECT_INDEX_PRICE_TASK: Final = "price_tracker.collect_index_price"
_MAX_RETRY_DELAY_SECONDS: Final = 30

type CollectIndexPriceTask = Task[[str], None]
type BeatSchedule = dict[str, dict[str, Any]]


def register_collect_task(
    app: Celery,
    collect: Callable[[Ticker], IndexPrice],
    settings: CollectorSettings,
) -> CollectIndexPriceTask:
    @app.task(
        name=COLLECT_INDEX_PRICE_TASK,
        autoretry_for=(ExchangeUnavailableError, StorageUnavailableError),
        max_retries=settings.max_retries,
        retry_backoff=True,
        retry_backoff_max=_MAX_RETRY_DELAY_SECONDS,
        retry_jitter=True,
    )
    def collect_index_price(ticker: str) -> None:
        collect(Ticker(ticker))

    return collect_index_price


def build_beat_schedule(settings: CollectorSettings) -> BeatSchedule:
    return {
        f"collect-{ticker}-index-price": {
            "task": COLLECT_INDEX_PRICE_TASK,
            "schedule": float(settings.interval_seconds),
            "args": (ticker.value,),
            "options": {"expires": settings.interval_seconds},
        }
        for ticker in settings.tickers
    }
