"""MANARA-BACKEND-SQLITE-WAL-FIX-01 — concurrency regression tests.

These tests prove that the file-backed SQLite engine configuration
(WAL + busy_timeout=15000 + synchronous=NORMAL) is:

1. Actually applied on every fresh DB-API connection (not just the first).
2. Stable under concurrent reads + writes that mimic the real browser
   workload (1 long compose + many parallel /status + /investigations reads).

The tests use a file-backed SQLite DB (NOT in-memory) because WAL is a
no-op on in-memory databases.

They run against the SAME uvicorn-backed FastAPI app the browser uses,
via TestClient's thread-pool mode, AND via direct ThreadPoolExecutor
concurrency against the live TestClient.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Force a file-backed SQLite DB (WAL is a no-op on :memory:). The session-scoped
# `engine` fixture in conftest.py already drops/creates tables on a file DB at
# /tmp/manara_test.db; we just verify it really is file-backed here.
from manara.config import settings
from manara.db.session import _is_in_memory_sqlite, get_engine


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pragma verification
# ─────────────────────────────────────────────────────────────────────────────


def test_is_in_memory_sqlite_detector_is_correct() -> None:
    """The _is_in_memory_sqlite helper must correctly classify URLs."""
    assert _is_in_memory_sqlite("sqlite:///:memory:") is True
    assert _is_in_memory_sqlite("sqlite::memory:") is True
    assert _is_in_memory_sqlite("sqlite:///./manara_dev.db") is False
    assert _is_in_memory_sqlite("sqlite:////tmp/manara_test.db") is False
    assert _is_in_memory_sqlite("postgresql://u:p@h/db") is False


def test_file_backed_sqlite_has_wal_enabled(engine) -> None:
    """The test DB must be file-backed (per conftest) and WAL must be active."""
    assert settings.is_sqlite, "tests must run against SQLite"
    assert not _is_in_memory_sqlite(settings.database_url), (
        f"conftest must use a file-backed SQLite URL for WAL tests, got {settings.database_url}"
    )

    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
        synchronous = conn.execute(text("PRAGMA synchronous")).scalar()

    assert journal_mode == "wal", (
        f"file-backed SQLite must run in WAL mode, got {journal_mode!r}"
    )
    assert busy_timeout == 15000, (
        f"busy_timeout must be 15000ms (covers cold-start compose), got {busy_timeout}"
    )
    assert synchronous == 1, (
        f"synchronous must be NORMAL (1) under WAL, got {synchronous}"
    )


def test_wal_pragma_applied_on_every_new_connection(engine) -> None:
    """WAL pragmas must be applied to every fresh DB-API connection, not just the first.

    SQLAlchemy pools connections; we want to ensure that even after pool
    recycling, a new raw connection still has WAL active.
    """
    # Force pool to give us fresh connections by disposing + reconnecting.
    engine.dispose()
    for _ in range(3):
        with engine.connect() as conn:
            j = conn.execute(text("PRAGMA journal_mode")).scalar()
            b = conn.execute(text("PRAGMA busy_timeout")).scalar()
            assert j == "wal", f"connection lost WAL mode: {j!r}"
            assert b == 15000, f"connection lost busy_timeout: {b!r}"


def test_wal_sidecar_files_created_after_write(engine) -> None:
    """After a write, the SQLite -wal sidecar file must exist (proves WAL is active).

    This is a stronger proof than just reading PRAGMA journal_mode: it shows
    WAL is actually being USED for the journal, not just configured.
    """
    db_path = settings.database_url.replace("sqlite:///", "")
    # Normalize: strip leading slash if absolute (sqlite:////abs → /abs)
    if db_path.startswith("/") and not Path(db_path).is_absolute():
        db_path = "/" + db_path.lstrip("/")

    # Perform a write to force WAL activity.
    # Use INSERT OR REPLACE so the test is idempotent across runs (the probe
    # table is not dropped by conftest between test sessions).
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS _wal_probe (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT OR REPLACE INTO _wal_probe (id) VALUES (1)"))
        conn.commit()

    # The -wal file should now exist (it may be checkpointed away if the
    # connection was closed, so we accept either wal OR shm existing)
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")
    assert wal_path.exists() or shm_path.exists(), (
        f"Neither WAL sidecar exists after write: {wal_path}, {shm_path}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Concurrent workload regression
# ─────────────────────────────────────────────────────────────────────────────


COMPOSE_BODY = {
    "query": (
        "Compare clinical outcomes of robotic versus manual prosthetic "
        "alignment in patients aged 60+ with osteoarthritis, focusing on "
        "long-term functional recovery metrics"
    )
}


def _do_compose(client: TestClient) -> tuple[int, float]:
    t0 = time.perf_counter()
    r = client.post("/mold-factory/compose", json=COMPOSE_BODY)
    return r.status_code, time.perf_counter() - t0


def _do_status(client: TestClient) -> tuple[int, float]:
    t0 = time.perf_counter()
    r = client.get("/status")
    return r.status_code, time.perf_counter() - t0


def _do_list_investigations(client: TestClient) -> tuple[int, float]:
    t0 = time.perf_counter()
    r = client.get("/mold-factory/investigations")
    return r.status_code, time.perf_counter() - t0


def test_concurrent_status_and_reads_do_not_block_or_fail(client) -> None:
    """Concurrent /status + /investigations reads must all succeed.

    Under WAL, readers do not block on each other or on a single writer.
    """
    results: list[tuple[str, int, float]] = []
    lock = threading.Lock()

    def worker(label: str, fn) -> None:
        st, dur = fn(client)
        with lock:
            results.append((label, st, dur))

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = []
        for _ in range(20):
            futures.append(ex.submit(worker, "status", _do_status))
        for _ in range(20):
            futures.append(ex.submit(worker, "list_inv", _do_list_investigations))
        for f in as_completed(futures):
            f.result()

    assert len(results) == 40
    statuses = {r[1] for r in results}
    assert statuses == {200}, f"expected all 200, got {statuses}"
    # All reads should complete in well under 1s each under WAL
    max_dur = max(r[2] for r in results)
    assert max_dur < 5.0, f"some read took too long: {max_dur:.2f}s"


def test_concurrent_compose_and_reads_stable(client) -> None:
    """1 compose + 12 concurrent reads must all succeed.

    This is the browser pattern: status polling + investigations polling
    happening WHILE a compose write is in flight.
    """
    # Warm up the embeddings model so compose is fast (we want to test
    # concurrency, not the embeddings cold-start path).
    warm = client.post("/mold-factory/compose", json=COMPOSE_BODY)
    assert warm.status_code == 200, f"warm-up failed: {warm.status_code}"

    results: list[tuple[str, int, float]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(label: str, fn) -> None:
        try:
            st, dur = fn(client)
            with lock:
                results.append((label, st, dur))
        except Exception as e:
            with lock:
                errors.append(f"{label}: {type(e).__name__}: {e}")

    stop = threading.Event()

    def reader_loop(label: str) -> None:
        while not stop.is_set():
            worker(label, _do_status)
            worker(label, _do_list_investigations)

    with ThreadPoolExecutor(max_workers=8) as ex:
        # 1 compose in flight
        compose_future = ex.submit(worker, "compose", _do_compose)
        # 7 reader threads looping
        reader_futures = [ex.submit(reader_loop, f"r{i}") for i in range(7)]

        # Wait for compose to finish, then stop readers
        compose_future.result(timeout=120)
        # Let readers run a bit more to test post-compose stability
        time.sleep(1.0)
        stop.set()
        for f in as_completed(reader_futures):
            f.result()

    assert not errors, f"unexpected errors: {errors[:5]}"
    statuses = {r[1] for r in results}
    assert statuses == {200}, f"expected all 200, got {statuses}"


def test_two_concurrent_compose_calls_both_succeed(client) -> None:
    """Two simultaneous compose writes must both succeed.

    SQLite WAL allows one writer at a time; the second must wait for the
    lock (within busy_timeout) and succeed. Under the previous default
    5s busy_timeout, a cold-start second compose could fail with
    SQLITE_BUSY. Under 15s, both must succeed.
    """
    # Warm up
    warm = client.post("/mold-factory/compose", json=COMPOSE_BODY)
    assert warm.status_code == 200

    results_box: list[tuple[int, float]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            st, dur = _do_compose(client)
            with lock:
                results_box.append((st, dur))
        except Exception as e:
            with lock:
                errors.append(f"{type(e).__name__}: {e}")

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(worker)
        f2 = ex.submit(worker)
        f1.result(timeout=120)
        f2.result(timeout=120)

    assert not errors, f"compose errors: {errors}"
    assert len(results_box) == 2
    for st, _ in results_box:
        assert st == 200, f"compose returned {st}"
