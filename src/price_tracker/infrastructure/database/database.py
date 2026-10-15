from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from price_tracker.infrastructure.database.errors import translate_connectivity_errors

_CONNECT_TIMEOUT_SECONDS: Final = 10
_STATEMENT_TIMEOUT_SECONDS: Final = 30


class Database:
    """Owns the connection pool and hands out sessions bound to it."""

    def __init__(self, url: URL | str) -> None:
        self._engine = create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args={
                "timeout": _CONNECT_TIMEOUT_SECONDS,
                "command_timeout": _STATEMENT_TIMEOUT_SECONDS,
            },
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._read_only_session_factory = async_sessionmaker(
            self._engine.execution_options(
                isolation_level="REPEATABLE READ",
                postgresql_readonly=True,
            ),
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def read_only_session(self) -> AsyncIterator[AsyncSession]:
        """Session that reads a single snapshot and that PostgreSQL forbids to write."""
        async with self._read_only_session_factory() as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Session committed when the block succeeds and rolled back when it raises."""
        async with self._session_factory() as session:
            yield session
            with translate_connectivity_errors():
                await session.commit()

    async def dispose(self) -> None:
        await self._engine.dispose()
