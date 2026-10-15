from decimal import Decimal


class DomainError(Exception):
    """Base class for violations of domain invariants."""


class InvalidIndexPriceError(DomainError):
    """Raised when an index price observation cannot exist in the domain."""


class InvalidPriceError(InvalidIndexPriceError):
    def __init__(self, price: Decimal) -> None:
        super().__init__(f"Index price must be a positive finite number, got {price}")
        self.price = price


class NegativeTimestampError(InvalidIndexPriceError):
    def __init__(self, timestamp: int) -> None:
        super().__init__(f"UNIX timestamp must not be negative, got {timestamp}")
        self.timestamp = timestamp


class InvalidTimeRangeError(DomainError):
    def __init__(self, start: int, end: int) -> None:
        super().__init__(f"Time range start ({start}) must not be after its end ({end})")
        self.start = start
        self.end = end
