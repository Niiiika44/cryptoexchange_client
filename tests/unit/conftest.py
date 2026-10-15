import os
from pathlib import Path
from typing import Final

import pytest
from pydantic import SecretStr

from price_tracker.config import DatabaseSettings, Settings

_SETTINGS_ENV_PREFIXES: Final = ("POSTGRES_", "REDIS_", "DERIBIT_", "COLLECTOR_")


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith(_SETTINGS_ENV_PREFIXES):
            monkeypatch.delenv(name)


@pytest.fixture
def settings() -> Settings:
    return Settings(database=DatabaseSettings(password=SecretStr("unused")))
