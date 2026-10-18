"""Tiny CLI entrypoints for MANARA development convenience.

These wrap common commands so the Makefile / README can call `manara-migrate`,
`manara-dev`, `manara-test` without long shell strings.
"""

from __future__ import annotations

import subprocess
import sys


def migrate() -> int:
    """Apply Alembic migrations to the configured DATABASE_URL."""
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    return subprocess.call(cmd)


def dev() -> int:
    """Start uvicorn with reload (development)."""
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "manara.app:create_app",
        "--factory",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    return subprocess.call(cmd)


def test() -> int:
    """Run the pytest suite."""
    return subprocess.call([sys.executable, "-m", "pytest", "-v"])


if __name__ == "__main__":
    raise SystemExit(migrate())
