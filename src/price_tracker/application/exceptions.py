from price_tracker.domain import Ticker


class ApplicationError(Exception):
    """Base class for errors raised while executing a use case."""


class PriceNotFoundError(ApplicationError):
    """The price was not collected."""
    def __init__(self, ticker: Ticker) -> None:
        super().__init__(f"No index prices have been collected for {ticker} yet")
        self.ticker = ticker


class InvalidPaginationError(ApplicationError):
    """Cannot perform pagination."""
    def __init__(self, limit: int, offset: int) -> None:
        super().__init__(f"Pagination requires limit >= 1 and offset >= 0, got {limit=} {offset=}")
        self.limit = limit
        self.offset = offset


class StorageUnavailableError(ApplicationError):
    """The price storage is unreachable or timed out; retrying may help."""

    def __init__(self) -> None:
        super().__init__("Price storage is temporarily unavailable")


class ExchangeError(ApplicationError):
    """Base class for failures to obtain data from a crypto exchange."""


class ExchangeUnavailableError(ExchangeError):
    """The exchange is unreachable or temporarily unable to respond; retrying may help."""

    def __init__(self, exchange: str) -> None:
        super().__init__(f"{exchange} is temporarily unavailable")
        self.exchange = exchange


class ExchangeResponseError(ExchangeError):
    """The exchange answered with an error or an unusable payload; retrying will not help."""

    def __init__(self, exchange: str, detail: str) -> None:
        super().__init__(f"{exchange} returned an unusable response: {detail}")
        self.exchange = exchange
        self.detail = detail
