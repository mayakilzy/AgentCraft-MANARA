"""Search Foundry package — source discovery, sandbox testing, promotion.

Public API:
* :class:`FoundryService` — the coordinator (discover → assess → sandbox → approve)
* :class:`OpenAlexConnector` — first real connector implementation
* :class:`SafeHttpClient` — SSRF-protected HTTP client
* :data:`OPENALEX`, :data:`CATALOG` — candidate source catalog
"""

from manara.foundry.catalog import (
    ARXIV,
    CATALOG,
    CROSSREF,
    OPENALEX,
    SourceCandidate,
    get_candidate,
)
from manara.foundry.openalex_connector import (
    CONNECTOR_ID,
    CONNECTOR_VERSION,
    IMPLEMENTATION_SHA,
    FoundryCallRecord,
    OpenAlexConnector,
    SearchWorksResponse,
    WorkAuthorship,
    WorkResult,
)
from manara.foundry.safe_http import (
    FoundryRequestConfig,
    SafeHttpClient,
    SsrfViolation,
    validate_url,
)
from manara.foundry.service import (
    FoundryApprovalResult,
    FoundryService,
    SandboxTestResult,
)

__all__ = [
    "ARXIV",
    "CATALOG",
    "CONNECTOR_ID",
    "CONNECTOR_VERSION",
    "CROSSREF",
    "FoundryApprovalResult",
    "FoundryCallRecord",
    "FoundryRequestConfig",
    "FoundryService",
    "IMPLEMENTATION_SHA",
    "OPENALEX",
    "OpenAlexConnector",
    "SafeHttpClient",
    "SandboxTestResult",
    "SearchWorksResponse",
    "SourceCandidate",
    "SsrfViolation",
    "WorkAuthorship",
    "WorkResult",
    "get_candidate",
    "validate_url",
]
