import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from price_tracker.config import DatabaseSettings
from price_tracker.infrastructure.database import Base


def run_migrations_offline() -> None:
    context.configure(
        url=DatabaseSettings().url.render_as_string(hide_password=False),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(DatabaseSettings().url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def main() -> None:
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)

    # A caller that already holds a connection (e.g. the test suite) passes it in.
    connection = config.attributes.get("connection")
    if context.is_offline_mode():
        run_migrations_offline()
    elif connection is not None:
        _run_migrations(connection)
    else:
        asyncio.run(run_migrations_online())


main()
