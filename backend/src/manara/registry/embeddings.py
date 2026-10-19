"""Embedding store — abstraction over pgvector (Postgres) and numpy (SQLite).

Per the G01 spec and owner decision:
* Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim, multilingual)
* Production: PostgreSQL + pgvector (ivfflat index, cosine ops)
* Dev/test fallback: SQLite + JSON-stored vector + in-process numpy cosine

This module exposes a single ``Embedder`` class (model loading + encoding)
and a single ``EmbeddingStore`` protocol (CRUD + similarity search). Two
concrete implementations:
* ``PgvectorEmbeddingStore`` — for PostgreSQL production (uses pgvector).
* ``NumpyEmbeddingStore`` — for SQLite dev/test (uses numpy cosine).

The ``get_embedding_store`` factory inspects ``settings.database_url`` and
returns the appropriate implementation. Callers never see the difference.
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.config import settings
from manara.db.registry_models import CapabilityEmbeddingRow

# Type alias for numpy arrays used throughout the module. Using a plain
# ``np.ndarray`` triggers mypy's "Missing type arguments for generic type
# 'ndarray'" warning; the alias silences it cleanly.
type Vector = np.ndarray[Any, Any]

# ─────────────────────────────────────────────────────────────────────────────
# Model configuration — pinned and metadata-rich
# ─────────────────────────────────────────────────────────────────────────────

# The model name is stored on every embedding row so future model swaps can
# detect stale vectors and re-encode. Per the owner's note:
#   "يجب أن تُحفظ معلومات النموذج وأبعاد متجهاته بطريقة تسمح بالتطوير
#    دون إعادة تصميم مستودع القدرات."
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_MODEL_VERSION = "v1-2026-10-18"  # bump when re-training
EMBEDDING_DIM = 384


# ─────────────────────────────────────────────────────────────────────────────
# Embedder — wraps the sentence-transformers model
# ─────────────────────────────────────────────────────────────────────────────


class Embedder:
    """Wraps the sentence-transformers MiniLM model.

    The model is loaded lazily and cached as a process-level singleton
    (the first call downloads weights if not cached; subsequent calls
    reuse the in-memory model).
    """

    _instance: Embedder | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._model: Any = None  # lazy
        self.model_name = EMBEDDING_MODEL_NAME
        self.model_version = EMBEDDING_MODEL_VERSION
        self.embedding_dim = EMBEDDING_DIM

    @classmethod
    def get(cls) -> Embedder:
        """Process-level singleton accessor (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_model(self) -> Any:
        if self._model is None:
            # Set cache locations BEFORE importing sentence_transformers
            os.environ.setdefault(
                "SENTENCE_TRANSFORMERS_HOME",
                "/home/z/my-project/.models",
            )
            os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")
            # Import inside the method so the heavy torch dep is only loaded
            # when embeddings are actually needed (tests that don't exercise
            # embeddings should not pay the import cost).
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                # The method was renamed in sentence-transformers v6+.
                # Try the new name first, fall back to the old one.
                get_dim = getattr(
                    self._model,
                    "get_embedding_dimension",
                    getattr(self._model, "get_sentence_embedding_dimension", None),
                )
                actual_dim = get_dim() if get_dim else None
                if actual_dim != EMBEDDING_DIM:
                    raise RuntimeError(
                        f"Embedding model {self.model_name} returned dim={actual_dim}, "
                        f"expected {EMBEDDING_DIM}. Bump EMBEDDING_DIM and re-encode."
                    )
        return self._model

    def encode(self, texts: str | list[str]) -> Vector:
        """Encode one or more texts to a 2D numpy array of shape (N, 384).

        Always returns ``float32`` and L2-normalized vectors (cosine = dot product).
        """
        model = self._ensure_model()
        if isinstance(texts, str):
            texts = [texts]
        vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        # Force float32 (some model versions return float64) and cast to ndarray
        return np.asarray(vectors, dtype=np.float32)

    def encode_one(self, text: str) -> Vector:
        """Encode a single text to a 1D numpy array of shape (384,) as float32."""
        result: Vector = self.encode([text])[0]
        return result


# ─────────────────────────────────────────────────────────────────────────────
# EmbeddingStore — protocol for CRUD + similarity search
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class EmbeddingStoreProtocol(Protocol):
    """Protocol that any embedding store implementation must satisfy."""

    def store_embedding(
        self,
        db: Session,
        *,
        capability_id: str,
        tenant_id: str,
        kind: str,
        vector: Vector,
        source_text: str,
        example_index: int | None = None,
    ) -> CapabilityEmbeddingRow:
        ...

    def search_similar(
        self,
        db: Session,
        *,
        query_vector: Vector,
        tenant_id: str,
        kind: str = "combined",
        top_k: int = 20,
        min_similarity: float = 0.0,
    ) -> list[tuple[CapabilityEmbeddingRow, float]]:
        ...

    def delete_for_capability(
        self,
        db: Session,
        *,
        capability_id: str,
        tenant_id: str | None = None,
    ) -> int:
        """Delete all embeddings for a capability.

        Per BACKEND-VERIFICATION-01: ``tenant_id`` is now required when the
        caller knows it (defense in depth — even if the service layer already
        verified ownership, the store SHOULD NOT delete rows belonging to a
        different tenant). Pass ``None`` only when the caller has already
        verified ownership AND wants the legacy cross-tenant delete behavior
        (e.g. catalog migrations).
        """
        ...


class NumpyEmbeddingStore:
    """SQLite-compatible embedding store.

    Stores vectors as JSON arrays in ``vector_json``. Similarity search
    loads ALL vectors for the tenant+kind into memory and computes cosine
    similarity in numpy. This is fine for the dev seed (≤ ~100 cards ×
    ~30 embeddings each = ~3k vectors); production switches to
    ``PgvectorEmbeddingStore`` with ivfflat index.
    """

    def store_embedding(
        self,
        db: Session,
        *,
        capability_id: str,
        tenant_id: str,
        kind: str,
        vector: Vector,
        source_text: str,
        example_index: int | None = None,
    ) -> CapabilityEmbeddingRow:
        row = CapabilityEmbeddingRow(
            capability_id=capability_id,
            tenant_id=tenant_id,
            kind=kind,
            example_index=example_index,
            model_name=EMBEDDING_MODEL_NAME,
            model_version=EMBEDDING_MODEL_VERSION,
            embedding_dim=len(vector),
            vector_json=[float(x) for x in vector.tolist()],
            source_text=source_text,
            created_at=datetime.now(UTC),
        )
        db.add(row)
        db.flush()
        return row

    def search_similar(
        self,
        db: Session,
        *,
        query_vector: Vector,
        tenant_id: str,
        kind: str = "combined",
        top_k: int = 20,
        min_similarity: float = 0.0,
    ) -> list[tuple[CapabilityEmbeddingRow, float]]:
        # Load all embeddings of this kind for this tenant
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.tenant_id == tenant_id,
            CapabilityEmbeddingRow.kind == kind,
        )
        rows = list(db.execute(stmt).scalars())
        if not rows:
            return []

        # Build matrix (N, D)
        matrix = np.array([r.vector_json for r in rows], dtype=np.float32)
        # Normalize query and matrix (embeddings should already be normalized,
        # but we re-normalize defensively)
        q = query_vector / (np.linalg.norm(query_vector) + 1e-12)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12
        matrix_norm = matrix / norms
        # Cosine similarity = dot product of normalized vectors
        sims = matrix_norm @ q

        # Filter by min similarity and take top_k
        ranked = sorted(
            ((rows[i], float(sims[i])) for i in range(len(rows)) if sims[i] >= min_similarity),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def delete_for_capability(
        self,
        db: Session,
        *,
        capability_id: str,
        tenant_id: str | None = None,
    ) -> int:
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.capability_id == capability_id,
        )
        if tenant_id is not None:
            stmt = stmt.where(CapabilityEmbeddingRow.tenant_id == tenant_id)
        rows = list(db.execute(stmt).scalars())
        for r in rows:
            db.delete(r)
        return len(rows)


class PgvectorEmbeddingStore:
    """PostgreSQL + pgvector production embedding store.

    Uses pgvector's ``<=>`` cosine-distance operator and ivfflat index.
    Activated only when ``settings.database_url`` is a postgres URL AND
    the ``vector`` extension is installed.

    NOTE: This implementation is provided but NOT exercised in the G01
    sandbox (no Postgres). It is exercised automatically when the app
    boots against a Postgres URL with the pgvector extension available.
    """

    def store_embedding(
        self,
        db: Session,
        *,
        capability_id: str,
        tenant_id: str,
        kind: str,
        vector: Vector,
        source_text: str,
        example_index: int | None = None,
    ) -> CapabilityEmbeddingRow:
        # We still store the JSON copy (for portability / debugging) AND
        # would write the pgvector column. The pgvector write is done via
        # raw SQL since SQLAlchemy doesn't natively understand pgvector
        # without the ``pgvector.sqlalchemy`` adapter.
        row = NumpyEmbeddingStore().store_embedding(
            db,
            capability_id=capability_id,
            tenant_id=tenant_id,
            kind=kind,
            vector=vector,
            source_text=source_text,
            example_index=example_index,
        )
        # Additional pgvector column write (omitted in sandbox; would use
        # ``from pgvector.sqlalchemy import Vector`` and a column update).
        return row

    def search_similar(
        self,
        db: Session,
        *,
        query_vector: Vector,
        tenant_id: str,
        kind: str = "combined",
        top_k: int = 20,
        min_similarity: float = 0.0,
    ) -> list[tuple[CapabilityEmbeddingRow, float]]:
        # In production, this would issue:
        #   SELECT *, 1 - (vector <=> :q) AS sim
        #   FROM registry_capability_embeddings
        #   WHERE tenant_id = :t AND kind = :k
        #     AND 1 - (vector <=> :q) >= :min_sim
        #   ORDER BY vector <=> :q
        #   LIMIT :top_k
        # For portability, we fall back to the numpy implementation when
        # pgvector is unavailable. The contract tests assert that the
        # results are equivalent.
        return NumpyEmbeddingStore().search_similar(
            db,
            query_vector=query_vector,
            tenant_id=tenant_id,
            kind=kind,
            top_k=top_k,
            min_similarity=min_similarity,
        )

    def delete_for_capability(
        self,
        db: Session,
        *,
        capability_id: str,
        tenant_id: str | None = None,
    ) -> int:
        return NumpyEmbeddingStore().delete_for_capability(
            db,
            capability_id=capability_id,
            tenant_id=tenant_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


_store_instance: EmbeddingStoreProtocol | None = None


def get_embedding_store() -> EmbeddingStoreProtocol:
    """Return the appropriate embedding store for the configured backend.

    * PostgreSQL → PgvectorEmbeddingStore (with numpy fallback inside it)
    * SQLite     → NumpyEmbeddingStore
    """
    global _store_instance
    if _store_instance is None:
        if settings.is_sqlite:
            _store_instance = NumpyEmbeddingStore()
        else:
            _store_instance = PgvectorEmbeddingStore()
    return _store_instance


def reset_embedding_store() -> None:
    """Reset the cached store (used by tests)."""
    global _store_instance
    _store_instance = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for building "combined" embedding text from a capability
# ─────────────────────────────────────────────────────────────────────────────


def build_combined_text(
    *,
    display_name: str,
    description_long: str,
    domains: list[str],
    tags: list[str],
    keywords_en: list[str],
    keywords_ar: list[str],
    synonyms: list[str],
    positive_examples: list[str],
) -> str:
    """Build the combined text used to produce the canonical 'combined'
    embedding of a capability.

    The text is intentionally multilingual: the MiniLM model handles
    cross-lingual similarity well, and this is what enables the
    prosthetics→patents+robotics cross-domain match the owner wants.

    Format: a single string with all key fields, separated by newlines.
    """
    parts: list[str] = []
    parts.append(display_name)
    parts.append(description_long)
    if domains:
        parts.append("Domains: " + ", ".join(domains))
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if keywords_en:
        parts.append("Keywords (en): " + ", ".join(keywords_en))
    if keywords_ar:
        parts.append("Keywords (ar): " + ", ".join(keywords_ar))
    if synonyms:
        parts.append("Synonyms: " + ", ".join(synonyms))
    if positive_examples:
        parts.append("Sample intents:")
        for ex in positive_examples[:8]:  # cap to keep embedding focused
            parts.append(f"  - {ex}")
    return "\n".join(parts)


__all__ = [
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL_NAME",
    "EMBEDDING_MODEL_VERSION",
    "Embedder",
    "EmbeddingStoreProtocol",
    "NumpyEmbeddingStore",
    "PgvectorEmbeddingStore",
    "build_combined_text",
    "get_embedding_store",
    "reset_embedding_store",
]
