"""MANARA application configuration.

All settings come from environment variables. NO hardcoded secrets. The
default profile is ``development`` and uses SQLite as a lightweight dev
variant per the G00 spec ("lightweight dev variant permitted if
integration is ready"). PostgreSQL is the production target.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for MANARA backend.

    The ``.env`` file (NEVER committed) overrides these defaults.
    ``.env.example`` documents every key and is the canonical placeholder.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime ──────────────────────────────────────────────────────────────
    env: Literal["development", "staging", "production"] = Field(
        default="development", alias="MANARA_ENV"
    )
    log_level: str = Field(default="INFO", alias="MANARA_LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="MANARA_HOST")
    port: int = Field(default=8000, alias="MANARA_PORT")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./manara_dev.db",
        alias="DATABASE_URL",
        description="PostgreSQL in production; SQLite for tests/dev variant.",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    # ── Frontend ──────────────────────────────────────────────────────────────
    frontend_base_url: str = Field(default="http://localhost:5173", alias="FRONTEND_BASE_URL")

    # ── Tenancy / Security (G00: single-tenant demo) ────────────────────────
    single_tenant_demo: bool = Field(default=True, alias="MANARA_SINGLE_TENANT_DEMO")
    default_tenant_id: str = Field(default="tenant_demo", alias="MANARA_DEFAULT_TENANT_ID")

    # ── Discovery mode (G00: synthetic-only) ────────────────────────────────
    discovery_mode: Literal["synthetic", "live"] = Field(
        default="synthetic",
        alias="MANARA_DISCOVERY_MODE",
        description="G00 ships with synthetic only; live mode arrives in G02.",
    )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (FastAPI dependency-friendly)."""
    return Settings()


# Re-export for convenience
settings = get_settings()


# ── Application metadata ─────────────────────────────────────────────────────
APP_NAME = "MANARA"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = (
    "MANARA — Adaptive Intelligence Factory. "
    "G00 engineering foundation: typed contracts, minimal API scaffold, "
    "synthetic-only discovery. NOT a working intelligence engine yet."
)

# Build metadata used by the /status endpoint
BUILD_INFO: dict[str, str] = {
    "mission": "G00",
    "foundation_version": "1.0",
    "schema_versions": "see /contracts/schemas",
    "code_repository": "https://github.com/mayakilzy/AgentCraft-MANARA",
    "specs_repository": "https://github.com/mayakilzy/repo-info/tree/main/AgentCraft-MANARA",
}


def reload_settings() -> Settings:
    """Force settings reload (used by tests that change env vars)."""
    get_settings.cache_clear()
    return get_settings()


__all__ = [
    "APP_DESCRIPTION",
    "APP_NAME",
    "APP_VERSION",
    "BUILD_INFO",
    "Settings",
    "get_settings",
    "reload_settings",
    "settings",
]


# Ensure tests can detect when settings have been mutated via env
def _env_truth(key: str) -> str | None:
    return os.environ.get(key)
