import pytest

from price_tracker.application import InvalidPaginationError, Pagination


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (-1, 0), (1, -1)])
def test_pagination_rejects_empty_window_and_negative_offset(limit: int, offset: int) -> None:
    with pytest.raises(InvalidPaginationError):
        Pagination(limit=limit, offset=offset)
