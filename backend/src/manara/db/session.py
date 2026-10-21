"""SQLAlchemy declarative base + session factory.

G00 ships SQLite as a lightweight dev variant; PostgreSQL remains the
production target. Models are deliberately kept thin: the Pydantic
contracts in :mod:`manara.contracts` are the authoritative schema, while
these ORM models exist only to demonstrate end-to-end persistence of the
``Investigation`` row (the canonical tenant-scoped entity). Full ORM
mirroring of every contract is deferred to G03 (cumulative memory).

MANARA-BACKEND-SQLITE-WAL-FIX-01
---------------------------------
For FILE-BACKED SQLite only, the engine now explicitly enables:

* ``PRAGMA journal_mode=WAL``      — lets readers proceed concurrently with
  a single writer (rollback-journal mode blocks all readers during a write).
* ``PRAGMA busy_timeout=15000``    — wait up to 15 s for a lock before
  raising ``SQLITE_BUSY``. The previous implicit default was 5 s, which is
  shorter than a cold-start compose transaction (~13 s while the
  sentence-transformers model is loaded inside the write transaction).
* ``PRAGMA synchronous=NORMAL``    — safe under WAL; cuts fsync cost.

In-memory SQLite (``sqlite:///:memory:`` and ``sqlite::memory:``) is left
untouched — WAL on a private in-memory database is a no-op and would just
add noise to test logs.

The pragmas are issued from a ``connect`` event listener, OUTSIDE any
active transaction, on every fresh DB-API connection. They are NOT issued
inside ``Session.begin()`` / ``Session.commit()`` so they cannot interfere
with application-level transaction boundaries.

PostgreSQL engines are unaffected: no event listener is registered and the
``pool_size`` / ``max_overflow`` knobs remain as before.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from manara.config import settings


class Base(DeclarativeBase):
    """Declarative base for all MANARA ORM models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _is_in_memory_sqlite(url: str) -> bool:
    """Return True for an in-memory SQLite URL.

    Accepts both the canonical ``sqlite:///:memory:`` form and the rare
    ``sqlite::memory:`` form. File-backed URLs (``sqlite:///./foo.db``,
    ``sqlite:////abs/path/foo.db``) return False.
    """
    if not url.startswith("sqlite"):
        return False
    rest = url[len("sqlite:"):]
    return rest.lstrip("/").startswith(":memory:") or rest == ":memory:"


def _configure_file_backed_sqlite(dbapi_conn, _connection_record) -> None:
    """Apply WAL + busy_timeout + synchronous=NORMAL on a fresh file-backed SQLite conn.

    Called by SQLAlchemy's ``connect`` event listener. Runs OUTSIDE any
    active transaction (SQLite PRAGMAs that affect the journal mode must
    not be issued inside a BEGIN..COMMIT block).
    """
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.execute("PRAGMA synchronous=NORMAL")
    finally:
        cur.close()


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
        # WAL + busy_timeout only for FILE-BACKED SQLite.
        # In-memory SQLite is used by some unit tests and would be unaffected
        # by WAL anyway (the journal_mode pragma returns "memory" silently).
        if settings.is_sqlite and not _is_in_memory_sqlite(settings.database_url):
            event.listen(_engine, "connect", _configure_file_backed_sqlite)
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
