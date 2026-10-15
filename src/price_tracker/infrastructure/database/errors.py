from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from sqlalchemy import exc

from price_tracker.application import StorageUnavailableError

_CONNECTIVITY_ERRORS: Final = (
    OSError,
    exc.TimeoutError,
    exc.OperationalError,
    exc.InterfaceError,
)


@contextmanager
def translate_connectivity_errors() -> Iterator[None]:
    """Report a storage that cannot be reached as ``StorageUnavailableError``."""
    try:
        yield
    except _CONNECTIVITY_ERRORS as error:
        raise StorageUnavailableError from error
    except exc.DBAPIError as error:
        if not error.connection_invalidated:
            raise
        raise StorageUnavailableError from error
