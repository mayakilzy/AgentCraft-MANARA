"""SQLAlchemy declarative base + session factory.

G00 ships SQLite as a lightweight dev variant; PostgreSQL remains the
production target. Models are deliberately kept thin: the Pydantic
contracts in :mod:`manara.contracts` are the authoritative schema, while
these ORM models exist only to demonstrate end-to-end persistence of the
``Investigation`` row (the canonical tenant-scoped entity). Full ORM
mirroring of every contract is deferred to G03 (cumulative memory).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from manara.config import settings


class Base(DeclarativeBase):
    """Declarative base for all MANARA ORM models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the lazily-created engine (per-process singleton)."""
    global _engine
    if _engine is None:
        kwargs: dict[str, Any] = {}
        if settings.is_sqlite:
            # SQLite needs check_same_thread=False for FastAPI workers
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_size"] = settings.database_pool_size
            kwargs["max_overflow"] = settings.database_max_overflow
        _engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            **kwargs,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the lazily-created session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def reset_engine() -> None:
    """Drop the cached engine/session (used by tests that swap DATABASE_URL)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a scoped session."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (used for SQLite dev / tests)."""
    # Import here so models register with Base before create_all.
    from manara.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


__all__ = [
    "Base",
    "get_db",
    "get_engine",
    "get_session_factory",
    "init_db",
    "reset_engine",
]
