from dataclasses import dataclass

from price_tracker.application.exceptions import InvalidPaginationError


@dataclass(frozen=True, slots=True, kw_only=True)
class Pagination:
    """Window over an ordered result set."""

    limit: int
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1 or self.offset < 0:
            raise InvalidPaginationError(self.limit, self.offset)


@dataclass(frozen=True, slots=True, kw_only=True)
class Page[ItemT]:
    """One window of a result set together with the size of the whole set."""

    items: tuple[ItemT, ...]
    total: int
    pagination: Pagination
