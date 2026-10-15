import pytest

from price_tracker.domain import InvalidTimeRangeError, TimeRange


def test_time_range_rejects_start_after_end() -> None:
    with pytest.raises(InvalidTimeRangeError):
        TimeRange(start=11, end=10)


def test_time_range_allows_single_moment() -> None:
    assert TimeRange(start=10, end=10).contains(10)


@pytest.mark.parametrize(
    ("time_range", "timestamp", "expected"),
    [
        (TimeRange(start=10, end=20), 10, True),
        (TimeRange(start=10, end=20), 20, True),
        (TimeRange(start=10, end=20), 9, False),
        (TimeRange(start=10, end=20), 21, False),
        (TimeRange(start=10), 1_000_000, True),
        (TimeRange(start=10), 9, False),
        (TimeRange(end=20), 0, True),
        (TimeRange(end=20), 21, False),
        (TimeRange.unbounded(), 0, True),
    ],
)
def test_time_range_contains_inclusive_bounds(
    time_range: TimeRange,
    timestamp: int,
    *,
    expected: bool,
) -> None:
    assert time_range.contains(timestamp) is expected
