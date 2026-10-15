import yarl
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SecretStr,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from price_tracker.domain import Ticker


def _from_env(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(env_prefix=prefix, env_file=".env", extra="ignore", frozen=True)


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection."""

    model_config = _from_env("POSTGRES_")

    host: str = "localhost"
    port: PositiveInt = 5432
    user: str = "postgres"
    password: SecretStr
    db: str = "price_tracker"

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )


class DeribitSettings(BaseSettings):
    """Deribit exchange settings."""
    model_config = _from_env("DERIBIT_")

    base_url: HttpUrl = HttpUrl("https://www.deribit.com/api/v2")
    request_timeout_seconds: PositiveFloat = 10.0


class RedisSettings(BaseSettings):
    """Redis as the Celery broker."""

    model_config = _from_env("REDIS_")

    host: str = "localhost"
    port: PositiveInt = 6379
    password: SecretStr | None = None
    db: NonNegativeInt = 0

    @property
    def url(self) -> str:
        password = None if self.password is None else self.password.get_secret_value()
        url = yarl.URL.build(
            scheme="redis",
            password=password,
            host=self.host,
            port=self.port,
            path=f"/{self.db}",
        )
        return str(url)


class CollectorSettings(BaseSettings):
    """What to collect and how often."""

    model_config = _from_env("COLLECTOR_")

    tickers: tuple[Ticker, ...] = Field(default=tuple(Ticker), min_length=1)
    interval_seconds: PositiveInt = 60
    max_retries: NonNegativeInt = 3


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    deribit: DeribitSettings = Field(default_factory=DeribitSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)
