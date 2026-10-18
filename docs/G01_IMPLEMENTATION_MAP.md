# G01 — Implementation Map (proposed, not approved)

> **Status**: Draft. The owner (Ayman) must approve before G01 starts.
> **Source**: `repo-info/AgentCraft-MANARA/MISSIONS/G01.md` + the roadmap.
> **Mission scope**: Capability Registry and semantic retrieval.

## Goal

Build the **Capability Registry** that the spec calls the "compounding asset":
a store of reviewed, richly-described, multilingual capability cards with
intent coverage, negative use cases, evaluation history, and graph
relationships. Plus the first **hybrid retrieval** (lexical + embedding) over
those cards — but ONLY over approved capability metadata, NOT over user
evidence (that arrives in G03).

## What G01 must deliver (mapped to G01.md)

1. **Registry tables** (PostgreSQL + Alembic migration):
   - `sources` (mirrors `Source` contract).
   - `connectors` (mirrors `Connector` contract).
   - `search_capabilities` (mirrors `SearchCapability` contract; the
     primary card surface).
   - `capability_evaluations` (mirrors `CapabilityEvaluation`).
   - `capability_relationships` (mirror of `CapabilityGraph` edges).
   - `approvals` (reviewer + rationale + timestamp).
2. **Rich search cards** (per `02_SEARCH/02_REGISTRY.md`):
   - 15–30 meaningful positive examples per high-value card.
   - Multilingual (ar/en) keywords + synonyms.
   - Deliberate negative examples (prevents misuse).
   - Source license + rights snapshot.
   - Evaluation history (dates, success/failure).
3. **Retrieval strategy** (per `01_ARCHITECTURE/02_CONTRACTS.md`):
   - Stage 1: metadata/tag/location/data-type/access-rights filter.
   - Stage 2: hybrid full-text + embedding search (pgvector) — but only over
     capability cards, NOT over evidence.
   - Stage 3: rerank by positive AND negative example similarity to query.
   - Stage 4: validate approved status + freshness; create candidate or
     report missing coverage.
   - Stage 5: benchmark queries for precision/recall.
4. **Registry API**:
   - `GET /registry/capabilities?intent=...&domain=...` — list + filter.
   - `GET /registry/capabilities/{id}` — fetch a single card.
   - `POST /registry/capabilities` — propose a new card (state=candidate).
   - `PATCH /registry/capabilities/{id}/approve` — owner-approved promotion.
5. **Tests**:
   - Contract tests for every new ORM table.
   - Hybrid retrieval precision/recall on a benchmark set (≥5 queries).
   - Negative-example misuse test (must NOT return a card whose negative
     examples match the query).
   - Tenant isolation: tenant A's private cards MUST NOT appear in tenant B's
     search results.
6. **Frontend**:
   - Registry browser: list cards, filter by domain/status, expand to inspect
     positive/negative examples, evaluations, source/license.

## Small milestones (recommended order)

1. **M01** (½ day): Alembic migration for the five new tables. Smoke test:
   insert + read one capability card via the ORM. ≤200 LOC.
2. **M02** (½ day): Registry API endpoints (CRUD + filters). Smoke test:
   round-trip a SearchCapability payload through `POST /registry/capabilities`
   and `GET /registry/capabilities/{id}`.
3. **M03** (1 day): Stage-1 metadata filter + Stage-2 full-text search
   (no embeddings yet). Test: filter returns only matching cards; full-text
   ranks by relevance.
4. **M04** (1 day): pgvector extension + embedding storage for capability
   *descriptions* and *positive examples* (NOT for evidence — that's G03).
   Hybrid retrieval. Test: precision@5 ≥ 0.6 on benchmark queries.
5. **M05** (1 day): Negative-example reranker. Test: a query that matches a
   card's negative examples is downranked or filtered.
6. **M06** (½ day): Approval workflow (owner promotes candidate → approved).
   Audit record with reviewer + rationale.
7. **M07** (½ day): Frontend registry browser (Vite + React). List + filter
   + inspect card details.
8. **M08** (½ day): Tenant isolation tests (positive + negative —
   cross-tenant leakage must be zero).

Total: ~5 development days.

## What G01 explicitly does NOT do

- No real connector execution (G02).
- No real evidence collection (G03).
- No semantic retrieval over user evidence (G03).
- No real source discovery or sandbox (G02).
- No forecasting (G06).
- No production deployment.

## Open questions for the owner

1. **Which embedding model?** The spec mentions pgvector but does not pick a
   model. Suggested default: a small multilingual model (e.g. `paraphrase-multilingual-MiniLM-L12-v2`)
   running locally, so no API key is required. Alternative: an API-based
   embedding model (OpenAI, Cohere, or Z.AI's embedding endpoint) — but that
   introduces a credentials requirement.
2. **How many seed cards?** Spec suggests 15–30 examples per card. How many
   cards should G01 ship with? Recommend: 5–8 high-quality cards covering
   the candidate catalog in `02_SEARCH/03_CATALOG_SEED.md` (academic,
   patents, bio/health, energy/EV, agriculture) — NOT the entire catalog.
3. **Embedding dimension**: 384 (MiniLM) vs 768 (larger) vs 1024+ (API).
   Smaller is faster and adequate for capability-card retrieval.
4. **Owner approval workflow**: Should candidate cards auto-approve after
   tests pass, or always require an explicit owner action? Recommend the
   latter for G01, per the spec's "Registry promotion is owner-approved".

## Handoff from G00

- All G00 contracts are stable (`schema_version == 1.0.0`). G01 will NOT
  modify their fields; only add ORM tables and API endpoints.
- The `FoundryState` enum already includes the candidate→approved path.
- The `CapabilityEvaluation` Pydantic model is ready to be persisted as a
  table row.
- The `CapabilityGraph` model is ready; G01 will materialize it as an edge
  table.
