from dataclasses import dataclass
from typing import Self

from price_tracker.domain.exceptions import InvalidTimeRangeError


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeRange:
    """Closed interval of UNIX timestamps; a missing bound leaves that side open.

    Attributes:
        start: Inclusive lower bound, or ``None`` for "since the beginning".
        end: Inclusive upper bound, or ``None`` for "up to now".
    """

    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise InvalidTimeRangeError(self.start, self.end)

    @classmethod
    def unbounded(cls) -> Self:
        return cls()

    def contains(self, timestamp: int) -> bool:
        is_after_start = self.start is None or timestamp >= self.start
        is_before_end = self.end is None or timestamp <= self.end
        return is_after_start and is_before_end
