"""Alembic environment for MANARA.

G00 ships with one initial migration that creates the ``investigations``
table (the only ORM model defined for G00). Future missions will add
tables for sources, connectors, capabilities, evidence, forecasts, etc.

Configuration is environment-aware: ``DATABASE_URL`` (or ``MANARA_DATABASE_URL``)
drives the connection; Alembic does NOT carry its own credential file.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from manara.config import settings

# Import models so they register with Base.metadata before autogenerate.
from manara.db import models  # noqa: F401
from manara.db.session import Base

config = context.config

# Inject DATABASE_URL from settings (no .ini credentials).
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
