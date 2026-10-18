"""Test configuration for MANARA backend.

Each test session uses an in-memory SQLite database (lightweight dev variant)
so tests are fast and isolated. We:
1. Override ``DATABASE_URL`` BEFORE importing the app.
2. Reset the cached engine so the new URL takes effect.
3. Create tables via ``Base.metadata.create_all``.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

# Use an isolated file-based SQLite DB for tests (file instead of :memory:
# because the FastAPI lifespan opens short-lived sessions in different threads).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _BACKEND_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Force test profile before importing manara.config
os.environ["MANARA_ENV"] = "development"
os.environ["MANARA_LOG_LEVEL"] = "WARNING"
os.environ["MANARA_DISCOVERY_MODE"] = "synthetic"
os.environ["DATABASE_URL"] = "sqlite:////tmp/manara_test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from manara.app import create_app  # noqa: E402
from manara.config import reload_settings  # noqa: E402
from manara.db.session import Base, get_engine, reset_engine  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return reload_settings()


@pytest.fixture(scope="session")
def engine(settings):
    """One engine per test session (file-based SQLite)."""
    reset_engine()
    eng = get_engine()
    # Ensure a clean slate at session start.
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    reset_engine()


@pytest.fixture()
def client(engine) -> Iterator[TestClient]:
    """Per-test client; tables are wiped between tests for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = create_app()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db_session(engine):
    """Direct DB session for tests that need to write rows."""
    from sqlalchemy.orm import Session

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
