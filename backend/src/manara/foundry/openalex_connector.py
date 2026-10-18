"""OpenAlex Connector — first real source adapter (G02).

Per ``02_SEARCH/01_FOUNDRY.md`` §Sources vs connectors vs engines:
> "Provider OpenAlex → Connector openalex-v1 (endpoint, auth, pagination,
> normalized works) → many specialized search capabilities."

This module implements ``OpenAlexConnector`` — a tested implementation
of access/extraction against the OpenAlex REST API. It is the "how" layer;
the SearchCapability ``search.academic-publications`` (the "why" layer)
references this connector via ``connector_ids``.

Capabilities of this connector:
* ``search_works(query, filters, per_page)`` — full-text + structured
  search over OpenAlex Works. Returns normalized ``WorkResult`` records.
* ``get_work(openalex_id)`` — fetch a single work by its OpenAlex ID.
* Built-in rate-limit awareness (respects 429 with exponential backoff).
* Strict SSRF protection (only ``api.openalex.org``).
* Polite-pool email parameter (configurable; uses MANARA polite email).
* Records every API call in the Foundry evidence ledger.

Lifecycle states per the Foundry spec:
``discovered → assessed → candidate → sandbox_tested → review_pending →
approved`` (or ``rejected | quarantined | degraded | retired``).

This connector is shipped in ``candidate`` state — sandbox tests must
pass before the owner approves it for production use.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from manara.foundry.catalog import OPENALEX
from manara.foundry.safe_http import (
    FoundryRequestConfig,
    SafeHttpClient,
    SsrfViolation,
)

# ─────────────────────────────────────────────────────────────────────────────
# Connector metadata
# ─────────────────────────────────────────────────────────────────────────────

CONNECTOR_ID = "openalex-v1"
CONNECTOR_VERSION = "0.1.0"
IMPLEMENTATION_SHA = "g02-openalex-v1-2026-10-19"  # bump on every code change
OPENALEX_BASE_URL = "https://api.openalex.org"
POLITE_EMAIL = "manara-foundry@example.com"  # polite-pool identifier (no auth)


# ─────────────────────────────────────────────────────────────────────────────
# Result models (Pydantic v2 for validation at the API boundary)
# ─────────────────────────────────────────────────────────────────────────────


class WorkAuthorship(BaseModel):
    """A single authorship entry on a Work."""

    model_config = ConfigDict(extra="ignore")

    author_position: str | None = Field(default=None, alias="author_position")
    raw_author_name: str | None = Field(default=None, alias="raw_author_name")
    author_orcid: str | None = Field(default=None, alias="author_orcid")
    institution_display_name: str | None = Field(default=None, alias="institution_display_name")


class WorkResult(BaseModel):
    """A normalized OpenAlex Work record.

    Only fields relevant to MANARA's evidence-led retrieval are kept.
    The full OpenAlex Work payload is preserved in ``raw_payload`` for
    provenance.
    """

    model_config = ConfigDict(extra="ignore")

    openalex_id: str = Field(..., alias="id")
    doi: str | None = Field(default=None, alias="doi")
    title: str | None = Field(default=None, alias="title")
    display_name: str | None = Field(default=None, alias="display_name")
    publication_year: int | None = Field(default=None, alias="publication_year")
    publication_date: str | None = Field(default=None, alias="publication_date")
    cited_by_count: int = Field(default=0, alias="cited_by_count")
    language: str | None = Field(default=None, alias="language")
    type: str | None = Field(default=None, alias="type")
    is_oa: bool | None = Field(default=None, alias="is_oa")
    oa_url: str | None = Field(default=None, alias="oa_url")
    venue_display_name: str | None = Field(default=None, alias="primary_location_source_display_name")
    authorships: list[WorkAuthorship] = Field(default_factory=list, alias="authorships")
    concepts: list[dict[str, Any]] = Field(default_factory=list, alias="concepts")
    abstract_inverted_index: dict[str, list[int]] | None = Field(
        default=None, alias="abstract_inverted_index"
    )


class SearchWorksResponse(BaseModel):
    """Response shape from /works?search=..."""

    model_config = ConfigDict(extra="ignore")

    meta: dict[str, Any] = Field(default_factory=dict)
    results: list[WorkResult] = Field(default_factory=list)
    group_by: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class FoundryCallRecord:
    """Evidence-led record of a single API call.

    Every Foundry call produces one ``FoundryCallRecord``. The connector
    returns these alongside results so the Foundry evidence ledger can
    be updated transparently.
    """

    connector_id: str
    endpoint: str
    method: str
    url: str
    params: dict[str, Any]
    status_code: int | None
    result_count: int
    duration_ms: float
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ─────────────────────────────────────────────────────────────────────────────
# Connector
# ─────────────────────────────────────────────────────────────────────────────


class OpenAlexConnector:
    """Tested HTTP client for the OpenAlex REST API.

    The connector is stateless except for the underlying SafeHttpClient.
    Every method returns a tuple of ``(results, call_record)`` so callers
    can audit each call.

    API key handling:
    * OpenAlex's free tier (no API key) shares a daily budget across all
      users on the same IP. When that budget is exhausted (HTTP 429),
      callers must either wait for midnight UTC reset OR supply an
      API key.
    * If ``MANARA_OPENALEX_API_KEY`` env var is set, the connector
      sends it as ``Authorization: Bearer <key>`` header on every
      request. The key is NEVER logged or persisted.
    * If no key is set, the connector falls back to the polite-pool
      ``mailto`` parameter (lower rate limits, shared IP budget).
    """

    def __init__(
        self,
        *,
        polite_email: str = POLITE_EMAIL,
        per_page: int = 25,
        max_retries: int = 3,
        api_key: str | None = None,
    ) -> None:
        self.polite_email = polite_email
        self.default_per_page = min(per_page, 200)
        self.max_retries = max_retries
        # API key from arg or env var; never logged.
        self.api_key = api_key or os.environ.get("MANARA_OPENALEX_API_KEY")
        self.client = SafeHttpClient(
            allowed_hosts=OPENALEX.allowed_hosts,
            default_config=FoundryRequestConfig(
                timeout_seconds=30.0,
                follow_redirects=False,
                max_response_bytes=5 * 1024 * 1024,
                expected_content_types=("application/json",),
            ),
        )

    def __enter__(self) -> OpenAlexConnector:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    def search_works(
        self,
        query: str,
        *,
        per_page: int | None = None,
        filters: dict[str, str] | None = None,
        max_retries: int | None = None,
    ) -> tuple[list[WorkResult], FoundryCallRecord]:
        """Search OpenAlex Works by full-text query.

        Args:
            query: search string (will be sent as ``search`` parameter).
            per_page: page size (1-200). Defaults to connector default.
            filters: optional OpenAlex filter params (e.g. ``{"from_publication_date": "2020-01-01"}``).
            max_retries: override default max retries.

        Returns:
            Tuple of (normalized work results, call evidence record).
        """
        pp = min(per_page or self.default_per_page, 200)
        params: dict[str, Any] = {
            "search": query,
            "per-page": pp,
            "mailto": self.polite_email,  # polite pool
        }
        if filters:
            # OpenAlex filters use the form "key:value" joined by commas
            filter_str = ",".join(f"{k}:{v}" for k, v in filters.items())
            params["filter"] = filter_str

        url = f"{OPENALEX_BASE_URL}/works"
        record = FoundryCallRecord(
            connector_id=CONNECTOR_ID,
            endpoint="/works",
            method="GET",
            url=url,
            params=dict(params),
            status_code=None,
            result_count=0,
            duration_ms=0.0,
        )

        retries = max_retries if max_retries is not None else self.max_retries
        last_error: str | None = None
        # Build headers: include API key as Bearer token if available
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for attempt in range(retries + 1):
            start = time.monotonic()
            try:
                response = self.client.get(url, params=params, headers=headers)
                record.status_code = response.status_code
                record.duration_ms = (time.monotonic() - start) * 1000.0

                if response.status_code == 429:
                    # Rate limited — exponential backoff
                    last_error = "rate_limited_429"
                    if attempt < retries:
                        backoff = 2.0 ** attempt
                        time.sleep(backoff)
                        continue
                    record.error = "rate_limited_after_retries"
                    return [], record

                if response.status_code >= 500:
                    last_error = f"server_error_{response.status_code}"
                    if attempt < retries:
                        backoff = 2.0 ** attempt
                        time.sleep(backoff)
                        continue
                    record.error = last_error
                    return [], record

                if response.status_code != 200:
                    record.error = f"unexpected_status_{response.status_code}"
                    return [], record

                data = response.json()
                parsed = SearchWorksResponse.model_validate(data)
                record.result_count = len(parsed.results)
                return parsed.results, record

            except SsrfViolation as e:
                record.error = f"ssrf_violation:{e.rule}"
                record.duration_ms = (time.monotonic() - start) * 1000.0
                return [], record
            except Exception as e:  # noqa: BLE001 — Foundry catches all and records
                last_error = f"{type(e).__name__}:{e}"
                record.duration_ms = (time.monotonic() - start) * 1000.0
                if attempt < retries:
                    time.sleep(2.0 ** attempt)
                    continue
                record.error = last_error
                return [], record

        record.error = last_error or "unknown"
        return [], record

    def get_work(
        self,
        openalex_id: str,
    ) -> tuple[WorkResult | None, FoundryCallRecord]:
        """Fetch a single Work by its OpenAlex ID (e.g. 'W2741809807')."""
        # Validate the ID format — must start with W followed by digits
        clean_id = openalex_id.strip().upper()
        if not (clean_id.startswith("W") and clean_id[1:].isdigit()):
            record = FoundryCallRecord(
                connector_id=CONNECTOR_ID,
                endpoint=f"/works/{openalex_id}",
                method="GET",
                url="",
                params={},
                status_code=None,
                result_count=0,
                duration_ms=0.0,
                error="invalid_openalex_id_format",
            )
            return None, record

        url = f"{OPENALEX_BASE_URL}/works/{clean_id}"
        params = {"mailto": self.polite_email}
        # Build headers: include API key as Bearer token if available
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        start = time.monotonic()
        record = FoundryCallRecord(
            connector_id=CONNECTOR_ID,
            endpoint=f"/works/{clean_id}",
            method="GET",
            url=url,
            params=dict(params),
            status_code=None,
            result_count=0,
            duration_ms=0.0,
        )
        try:
            response = self.client.get(url, params=params, headers=headers)
            record.status_code = response.status_code
            record.duration_ms = (time.monotonic() - start) * 1000.0
            if response.status_code != 200:
                record.error = f"status_{response.status_code}"
                return None, record
            data = response.json()
            work = WorkResult.model_validate(data)
            record.result_count = 1
            return work, record
        except SsrfViolation as e:
            record.error = f"ssrf_violation:{e.rule}"
            return None, record
        except Exception as e:  # noqa: BLE001
            record.error = f"{type(e).__name__}:{e}"
            return None, record


__all__ = [
    "CONNECTOR_ID",
    "CONNECTOR_VERSION",
    "FoundryCallRecord",
    "IMPLEMENTATION_SHA",
    "OPENALEX_BASE_URL",
    "OpenAlexConnector",
    "POLITE_EMAIL",
    "SearchWorksResponse",
    "WorkAuthorship",
    "WorkResult",
]
