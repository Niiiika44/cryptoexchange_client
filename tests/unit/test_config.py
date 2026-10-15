from pydantic import SecretStr

from price_tracker.config import DatabaseSettings, RedisSettings


def test_redis_url_escapes_password() -> None:
    settings = RedisSettings(host="redis", port=6379, password=SecretStr("p@ss/w:rd"), db=1)

    assert settings.url == "redis://:p%40ss%2Fw%3Ard@redis:6379/1"


def test_redis_url_without_password() -> None:
    assert RedisSettings(host="redis", password=None).url == "redis://redis:6379/0"


def test_secrets_stay_out_of_settings_repr() -> None:
    database = DatabaseSettings(password=SecretStr("db-secret"))
    redis = RedisSettings(password=SecretStr("redis-secret"))

    assert "db-secret" not in repr(database)
    assert "redis-secret" not in repr(redis)
    assert "db-secret" not in repr(database.url)
