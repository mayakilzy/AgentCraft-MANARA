"""MANARA Capability Registry (G01).

This package implements the "compounding asset" described in
``02_SEARCH/02_REGISTRY.md``: a store of reviewed, richly-described,
multilingual capability cards with intent coverage, negative use cases,
evaluation history, source/license/rights snapshots, and graph
relationships. Semantic retrieval uses MiniLM embeddings (384-dim,
multilingual) with hybrid text + vector search and negative-example
reranking.

Public API:
* :class:`CapabilityRegistry` — the service class
* :class:`Embedder` — wraps the MiniLM model
* :func:`get_embedding_store` — factory for the active store backend
* :data:`SEED_CAPABILITIES` — eight seed cards shipped with G01
"""

from manara.registry.embeddings import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_VERSION,
    Embedder,
    EmbeddingStoreProtocol,
    NumpyEmbeddingStore,
    PgvectorEmbeddingStore,
    build_combined_text,
    get_embedding_store,
    reset_embedding_store,
)
from manara.registry.seed_cards import DOMAIN_SIGNAL_MAP, SEED_CAPABILITIES
from manara.registry.service import (
    CapabilityRegistry,
    CapabilitySearchHit,
    CapabilitySearchResult,
    SearchStageTrace,
)

__all__ = [
    "DOMAIN_SIGNAL_MAP",
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL_NAME",
    "EMBEDDING_MODEL_VERSION",
    "Embedder",
    "EmbeddingStoreProtocol",
    "NumpyEmbeddingStore",
    "PgvectorEmbeddingStore",
    "CapabilityRegistry",
    "CapabilitySearchHit",
    "CapabilitySearchResult",
    "SearchStageTrace",
    "SEED_CAPABILITIES",
    "build_combined_text",
    "get_embedding_store",
    "reset_embedding_store",
]
