from celery import Celery

from price_tracker.config import Settings
from price_tracker.entrypoints.worker.collector import IndexPriceCollector
from price_tracker.entrypoints.worker.tasks import build_beat_schedule, register_collect_task


def create_celery_app(settings: Settings) -> Celery:
    app = Celery("price_tracker", broker=settings.redis.url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,
        worker_pool="threads",
        beat_schedule=build_beat_schedule(settings.collector),
    )
    register_collect_task(app, IndexPriceCollector(settings).collect, settings.collector)
    return app
