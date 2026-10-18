"""Pydantic ↔ ORM conversion for Capability Registry rows.

These helpers convert between the G00 Pydantic contracts (authoritative
schema) and the G01 ORM rows (denormalized for queryability).

Why a separate conversion layer? Because the ORM rows denormalize some
fields (domains_json, keywords_ar_json, etc.) for fast filtering, while
the Pydantic payload preserves the *full* contract. The conversion
guarantees both stay in sync.
"""

from __future__ import annotations

from manara.contracts import (
    CapabilityEvaluation,
    Connector,
    SearchCapability,
    Source,
)
from manara.db.registry_models import (
    CapabilityEvaluationRow,
    CapabilityRow,
    ConnectorRow,
    SourceRow,
)

# ─────────────────────────────────────────────────────────────────────────────
# Source ↔ SourceRow
# ─────────────────────────────────────────────────────────────────────────────


def source_to_row(source: Source, *, tenant_id: str) -> SourceRow:
    """Convert a Pydantic Source to an ORM SourceRow.

    ``tenant_id`` is provided externally because the Source contract carries
    ``owner_tenant`` (the owning tenant) but every row in the registry is
    scoped by the *requesting* tenant (which may be the same in single-
    tenant mode, but differs in multi-tenant).
    """
    return SourceRow(
        id=source.identity.id,
        tenant_id=tenant_id,
        display_name=source.identity.display_name,
        status=source.governance.status.value,
        domains_json=list(source.discovery.domains),
        payload=source.model_dump(mode="json"),
    )


def row_to_source(row: SourceRow) -> Source:
    """Reconstruct a Pydantic Source from an ORM SourceRow."""
    return Source.model_validate(row.payload)


# ─────────────────────────────────────────────────────────────────────────────
# Connector ↔ ConnectorRow
# ─────────────────────────────────────────────────────────────────────────────


def connector_to_row(connector: Connector, *, tenant_id: str) -> ConnectorRow:
    return ConnectorRow(
        id=connector.id,
        tenant_id=tenant_id,
        source_id=connector.source_id,
        display_name=connector.display_name,
        status=connector.governance.status.value,
        implementation_sha=connector.implementation_sha,
        payload=connector.model_dump(mode="json"),
    )


def row_to_connector(row: ConnectorRow) -> Connector:
    return Connector.model_validate(row.payload)


# ─────────────────────────────────────────────────────────────────────────────
# SearchCapability ↔ CapabilityRow
# ─────────────────────────────────────────────────────────────────────────────


def capability_to_row(cap: SearchCapability, *, tenant_id: str) -> CapabilityRow:
    """Convert a Pydantic SearchCapability to an ORM CapabilityRow.

    The full contract is preserved in ``payload``; the denormalized columns
    are extracted for fast filtering and full-text search.
    """
    return CapabilityRow(
        id=cap.id,
        tenant_id=tenant_id,
        display_name=cap.display_name,
        status=cap.status.value,
        version=cap.version,
        schema_version=cap.schema_version,
        domains_json=list(cap.domains),
        subdomains_json=list(cap.subdomains),
        tags_json=list(cap.tags),
        keywords_ar_json=list(cap.keywords_ar),
        keywords_en_json=list(cap.keywords_en),
        languages_json=list(cap.languages),
        search_purposes_json=list(cap.search_purposes),
        data_types_json=list(cap.data_types),
        coverage_geographies_json=list(cap.coverage_geographies),
        description_long=cap.description_long,
        positive_examples_json=list(cap.positive_examples),
        negative_examples_json=list(cap.negative_examples),
        synonyms_json=list(cap.synonyms),
        connector_ids_json=list(cap.connector_ids),
        source_license=cap.source_license,
        data_reuse_rights=cap.data_reuse_rights,
        commercial_rights=cap.commercial_rights,
        payload=cap.model_dump(mode="json"),
        approved_by=cap.approved_by,
        approved_at=None,  # set on promotion
    )


def row_to_capability(row: CapabilityRow) -> SearchCapability:
    """Reconstruct a Pydantic SearchCapability from an ORM CapabilityRow."""
    return SearchCapability.model_validate(row.payload)


def evaluation_to_row(
    ev: CapabilityEvaluation, *, capability_id: str, tenant_id: str
) -> CapabilityEvaluationRow:
    return CapabilityEvaluationRow(
        capability_id=capability_id,
        tenant_id=tenant_id,
        evaluated_at=ev.evaluated_at,
        evaluator=ev.evaluator,
        benchmark_query_set=ev.benchmark_query_set,
        precision=ev.precision,
        recall=ev.recall,
        false_positive_misuse_rate=ev.false_positive_misuse_rate,
        notes=ev.notes,
        payload=ev.model_dump(mode="json"),
    )


__all__ = [
    "capability_to_row",
    "connector_to_row",
    "evaluation_to_row",
    "row_to_capability",
    "row_to_connector",
    "row_to_source",
    "source_to_row",
]
