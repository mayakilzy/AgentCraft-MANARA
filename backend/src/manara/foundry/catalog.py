"""Source catalog for the Search Foundry (G02).

Per ``02_SEARCH/03_CATALOG_SEED.md``:
> "These are research candidates, not existing tested MANARA engines,
> guaranteed access, legal approvals, or live services."

This module enumerates candidate sources that the Foundry may discover,
evaluate, and (after sandbox testing + owner approval) promote into the
live registry. Each candidate carries enough metadata for a human or
automated reviewer to make a "should we build a connector?" decision.

The first real candidate (per owner decision, 2026-10-19) is OpenAlex —
a CC0-licensed open scholarly metadata catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class SourceCandidate:
    """A candidate source for the Foundry to evaluate."""

    id: str
    display_name: str
    homepage: str
    api_doc_url: str
    license: str
    data_reuse_rights: Literal["unknown", "read-only", "cache", "derivative", "commercial"]
    commercial_rights: Literal["unknown", "none", "non-commercial", "commercial-with-attribution", "commercial"]
    auth_required: bool
    rate_limit_policy: str
    allowed_hosts: list[str]
    primary_data_types: list[str]
    coverage_geographies: list[str]
    languages: list[str]
    description: str
    notes: str = ""


OPENALEX: SourceCandidate = SourceCandidate(
    id="openalex",
    display_name="OpenAlex",
    homepage="https://openalex.org",
    api_doc_url="https://docs.openalex.org",
    license="CC0-1.0 (Public Domain Dedication)",
    data_reuse_rights="cache",
    commercial_rights="commercial",
    auth_required=False,
    rate_limit_policy=(
        "Polite pool: 100,000 calls/day with mailto parameter in API request. "
        "Without mailto: ~10 calls/second, then throttled. No hard key required."
    ),
    allowed_hosts=["api.openalex.org"],
    primary_data_types=[
        "academic-works", "authors", "institutions", "venues",
        "concepts", "topics", "funders",
    ],
    coverage_geographies=["global"],
    languages=["en", "multi"],
    description=(
        "OpenAlex is a fully-open catalog of the global research system, "
        "started by the team behind Microsoft Academic Graph (MAG). It "
        "indexes ~250M works, 90M authors, 110K institutions, 200K venues. "
        "All metadata is CC0 (public domain dedication), so it can be "
        "freely cached, derived, and used commercially. No API key "
        "required; the polite-pool mailto parameter is optional but "
        "recommended for higher rate limits."
    ),
    notes=(
        "Owner-approved first real source for G02. Connector will use the "
        "Works endpoint (api.openalex.org/works) with search filters. "
        "Schema is stable; documented at docs.openalex.org."
    ),
)


CROSSREF: SourceCandidate = SourceCandidate(
    id="crossref",
    display_name="Crossref",
    homepage="https://www.crossref.org",
    api_doc_url="https://api.crossref.org/swagger-ui/",
    license="CC0-1.0 (metadata); content license varies by publisher",
    data_reuse_rights="cache",
    commercial_rights="commercial-with-attribution",
    auth_required=False,
    rate_limit_policy="Polite pool: ~50 requests/second with mailto.",
    allowed_hosts=["api.crossref.org"],
    primary_data_types=["dois", "metadata", "citations"],
    coverage_geographies=["global"],
    languages=["en", "multi"],
    description=(
        "Crossref is a non-profit registration agency for DOIs. ~150M "
        "metadata records. Free, public REST API; polite-pool mailto "
        "recommended."
    ),
    notes="Future candidate (G02+). Not yet sandbox-tested.",
)


ARXIV: SourceCandidate = SourceCandidate(
    id="arxiv",
    display_name="arXiv",
    homepage="https://arxiv.org",
    api_doc_url="https://info.arxiv.org/help/api/index.html",
    license="arXiv license (permissive reuse; some preprints carry publisher licenses)",
    data_reuse_rights="cache",
    commercial_rights="non-commercial",
    auth_required=False,
    rate_limit_policy="~1 request per 3 seconds recommended.",
    allowed_hosts=["export.arxiv.org"],
    primary_data_types=["preprints", "metadata"],
    coverage_geographies=["global"],
    languages=["en", "multi"],
    description="Open preprint repository, primarily STEM fields.",
    notes="Future candidate (G02+). Not yet sandbox-tested.",
)


CATALOG: list[SourceCandidate] = [
    OPENALEX,
    CROSSREF,
    ARXIV,
]


def get_candidate(candidate_id: str) -> SourceCandidate | None:
    """Look up a candidate by ID."""
    for c in CATALOG:
        if c.id == candidate_id:
            return c
    return None


__all__ = [
    "ARXIV",
    "CATALOG",
    "CROSSREF",
    "OPENALEX",
    "SourceCandidate",
    "get_candidate",
]
