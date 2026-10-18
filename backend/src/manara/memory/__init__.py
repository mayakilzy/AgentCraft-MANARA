"""MANARA Cumulative Knowledge Memory (G03).

Public API:
* :class:`MemoryCurator` — the cumulative knowledge curator
* :class:`LocalFilesystemStore`, :class:`S3CompatibleStore` — object stores
* :func:`get_object_store` — factory

Per ``03_INTELLIGENCE/01_KNOWLEDGE_MEMORY.md`` §Mission:
> "Investigations create reusable structured knowledge while filtering
> duplication, unsourced speculation, stale facts, and cross-tenant
> leakage. MANARA learns from every investigation, but trusts only what
> it can trace."
"""

from manara.memory.curator import (
    ClaimPromotionResult,
    ClaimRelation,
    ClaimVerdict,
    IngestResult,
    MemoryCurator,
    ReuseSearchResult,
)
from manara.memory.object_store import (
    LocalFilesystemStore,
    ObjectStoreProtocol,
    S3CompatibleStore,
    get_object_store,
    reset_object_store,
)

__all__ = [
    "ClaimPromotionResult",
    "ClaimRelation",
    "ClaimVerdict",
    "IngestResult",
    "LocalFilesystemStore",
    "MemoryCurator",
    "ObjectStoreProtocol",
    "ReuseSearchResult",
    "S3CompatibleStore",
    "get_object_store",
    "reset_object_store",
]
