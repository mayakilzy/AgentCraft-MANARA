"""MANARA FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from manara.api.errors import register_error_handlers
from manara.api.routes import (
    agents,
    contracts,
    discovery,
    foresight,
    foundry,
    memory,
    mold_factory,
    publishing,
    registry,
    status,
)
from manara.config import APP_DESCRIPTION, APP_NAME, APP_VERSION, settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: create tables for SQLite dev variant (no-op for Postgres).

    Production migrations use Alembic; this ``init_db`` call is a
    convenience for tests/dev variant so the API can run end-to-end
    without a separate migration step.
    """
    if settings.is_sqlite:
        # Import lazily so the SQLAlchemy engine is built with the live DATABASE_URL.
        from manara.db.session import init_db

        init_db()
    yield


def create_app() -> FastAPI:
    """Build the MANARA FastAPI app.

    The app is constructed via a factory so tests can build isolated
    instances with overridden dependencies.
    """
    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    # G00: permissive CORS for the local Vite dev server. G08 will tighten this.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,  # no auth in G00 yet
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Error handlers ────────────────────────────────────────────────────────
    register_error_handlers(app)

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(status.router)
    app.include_router(discovery.router)
    app.include_router(contracts.router)
    app.include_router(registry.router)
    app.include_router(foundry.router)
    app.include_router(memory.router)
    app.include_router(mold_factory.router)
    app.include_router(agents.router)
    app.include_router(foresight.router)
    app.include_router(publishing.router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """Root redirects informally to /status (kept out of OpenAPI schema)."""
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "see": "/status",
            "docs": "/docs",
            "discovery": "/discovery (synthetic only in G00)",
        }

    return app


# Module-level app instance for ``uvicorn manara.app:app``
app = create_app()


__all__ = ["app", "create_app"]
