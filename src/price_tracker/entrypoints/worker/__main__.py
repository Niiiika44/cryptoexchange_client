import sys

from price_tracker.config import Settings
from price_tracker.entrypoints.worker.app import create_celery_app


def main() -> None:
    create_celery_app(Settings()).start(argv=sys.argv[1:])


if __name__ == "__main__":
    main()
