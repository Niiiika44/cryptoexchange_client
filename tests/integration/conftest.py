import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Connection, NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from price_tracker.config import DatabaseSettings
from price_tracker.infrastructure.database import SqlAlchemyPriceRepository

ALEMBIC_CONFIG = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture(scope="session")
def database_url() -> URL:
    settings = DatabaseSettings()
    return settings.url.set(database=f"{settings.db}_test")


@pytest.fixture(scope="session", autouse=True)
def _migrated_database(database_url: URL) -> None:
    asyncio.run(_recreate_database(database_url))
    asyncio.run(_migrate(database_url))


@pytest.fixture
async def session(database_url: URL) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def repository(session: AsyncSession) -> SqlAlchemyPriceRepository:
    return SqlAlchemyPriceRepository(session)


async def _recreate_database(url: URL) -> None:
    maintenance_url = url.set(database="postgres")
    engine = create_async_engine(maintenance_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            name = connection.dialect.identifier_preparer.quote(str(url.database))
            await connection.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
            await connection.execute(text(f"CREATE DATABASE {name}"))
    finally:
        await engine.dispose()


async def _migrate(url: URL) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to_head)
    finally:
        await engine.dispose()


def _upgrade_to_head(connection: Connection) -> None:
    config = Config(ALEMBIC_CONFIG)
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
