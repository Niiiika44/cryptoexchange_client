from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Identity,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from price_tracker.domain import IndexPrice, Ticker


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


class IndexPriceRecord(Base):
    __tablename__ = "index_prices"
    __table_args__ = (
        UniqueConstraint("ticker", "timestamp"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("timestamp >= 0", name="timestamp_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(Numeric())
    timestamp: Mapped[int] = mapped_column(BigInteger, comment="UNIX timestamp, seconds")

    def to_entity(self) -> IndexPrice:
        return IndexPrice(ticker=Ticker(self.ticker), price=self.price, timestamp=self.timestamp)
