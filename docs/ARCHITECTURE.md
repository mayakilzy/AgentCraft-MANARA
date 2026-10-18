# Architecture — Code ↔ Spec Map

> **MANARA G00 · Engineering Foundation**
> This document maps the implemented code to the design specification at
> `https://github.com/mayakilzy/repo-info/tree/main/AgentCraft-MANARA`.

## Logical architecture (from `01_ARCHITECTURE/01_MASTER.md`)

```
User → Router → Mold Registry → (Mold Architect → Capability Registry →
        Search Foundry → Sandbox → Capability Registry → Mold Architect)
        → Investigation Execution → Agent Resolver → Search Orchestrator
        → Working Memory → Curator & Knowledge Memory → Forecast
        → Reports/Visuals → User
                ↓
        Immutable Run & Forecast Ledger
```

G00 implements **only the foundation** required to make the later missions
possible:

| Spec component              | G00 status | Code location                                  |
|------------------------------|------------|------------------------------------------------|
| Central Intent Router        | STUB       | (not yet implemented; investigation state machine is the closest analog) |
| Mold Registry                | CONTRACT   | `backend/src/manara/contracts/domain_mold.py`  |
| Mold Architect               | DEFERRED   | G04                                            |
| Capability Registry          | CONTRACT   | `backend/src/manara/contracts/search_capability.py` |
| Search Foundry               | DEFERRED   | G02                                            |
| Sandbox Validator            | DEFERRED   | G02                                            |
| Investigation Execution      | CONTRACT   | `backend/src/manara/contracts/investigation.py` |
| Agent Resolver               | CONTRACT   | `backend/src/manara/contracts/agent_recipe.py` |
| Search Orchestrator          | DEFERRED   | G02/G03                                        |
| Working Investigation Memory | DEFERRED   | G03                                            |
| Evidence Curator             | CONTRACT   | `backend/src/manara/contracts/evidence.py`    |
| Knowledge Memory             | DEFERRED   | G03                                            |
| Forecast Policy              | CONTRACT   | `backend/src/manara/contracts/forecast.py`    |
| Publishing                   | DEFERRED   | G07                                            |
| Immutable Run & Forecast Ledger | SCHEMA | `Forecast.published_at` + `subsequent_revision_of` immutability rule |

## Typed contracts (the eight foundational types)

Per `START-HERE.md`:
> "Establish clean layered modules and stable typed interfaces for Source,
> Connector, SearchCapability, DomainMold, AgentRecipe, Evidence, Forecast,
> Investigation; contract/schema tests and API smoke test."

| Type             | Pydantic model                                | Notes                                                            |
|------------------|-----------------------------------------------|------------------------------------------------------------------|
| Source           | `manara.contracts.Source`                     | identity / discovery / governance blocks; approved→approved_by  |
| Connector        | `manara.contracts.Connector`                  | execution block; credentials_ref is a vault ref, never raw bytes |
| SearchCapability | `manara.contracts.SearchCapability`           | graph + connector_ids invariant; positive AND negative examples |
| DomainMold       | `manara.contracts.Mold`                       | state machine temporary→reusable→maintained→archived             |
| AgentRecipe      | `manara.contracts.AgentRecipe`                | retention scores; tested/maintained require evaluation evidence |
| Evidence         | `manara.contracts.Evidence`                   | bitemporal provenance; never silently deleted (verdict enum)     |
| Forecast         | `manara.contracts.Forecast`                   | immutable at publication; insufficient_evidence forbids probs   |
| Investigation    | `manara.contracts.Investigation`              | ordered state transitions + checkpoint history                    |

Each contract carries a `schema_version` (currently `1.0.0` for all eight).
JSON Schemas are generated at runtime via `manara.contracts.json_schemas()`
and exposed at `/contracts/schemas`.

## API surface

| Endpoint             | Method | Purpose                                          |
|----------------------|--------|--------------------------------------------------|
| `/`                  | GET    | Informal root → points at /status, /docs          |
| `/status`            | GET    | Honest G00 build info + capabilities + not_impl  |
| `/health`            | GET    | Alias of `/status` (for health probes)            |
| `/discovery`         | GET    | One synthetic capability card (clearly labeled)   |
| `/contracts/schemas` | GET    | JSON Schemas for all eight contracts              |
| `/docs`              | GET    | Auto-generated OpenAPI                            |

## Persistence

- **Authoritative**: PostgreSQL (production target).
- **Dev variant**: SQLite (`sqlite:///./manara_dev.db`) — per G00 spec
  "lightweight dev variant permitted if integration is ready".
- **Migrations**: Alembic; one initial migration creates `investigations`.
- **ORM**: SQLAlchemy 2.x; only the Investigation row is modelled in G00.
  Full ORM mirroring arrives in G01 (Registry) and G03 (Memory).

## Security posture (G00)

- No secrets in code, configs, or test fixtures. `.env.example` carries only
  placeholders. `.env` is gitignored.
- `repo-info/START-HERE/GeneralGH.zip` is **not** an approved credential
  source and is never read.
- `credentials_ref` on `ConnectorExecution` is typed `str | None` and
  documented as a vault reference — never an inline secret.
- CORS is restricted to the Vite dev ports (`localhost:5173`).
- No authentication is wired in G00 (single-tenant demo mode). Multi-tenant
  enforcement arrives in G03 per the roadmap. Tenant scoping is *architected*
  (every contract carries `tenant_id`) but not *enforced* yet.
- Error envelope never leaks raw exceptions in production mode.

## Operational state machines

Encoded in `manara.lifecycle`:
- `FoundryState` — discovered → assessed → candidate → sandbox_tested →
  review_pending → approved (or rejected/quarantined/degraded/retired).
- `MoldState` — temporary → reusable → maintained → archived.
- `AgentState` — on_demand → recipe_saved → tested → maintained/retired.
- `InvestigationState` — received → scoped → coverage_checked →
  [building_capabilities?] → mold_ready → acquiring → normalizing →
  evidencing → forecasting_or_scenarios → drafting → verification →
  deliverable_ready → archived.

G00 ships the enums and transition tables; G02+ will add transition validators
that emit audit records with reasons (rejected/quarantined).

## What G00 explicitly does NOT do

Per `START-HERE.md` "Do not prematurely perform":
- No real source/connector calls.
- No forecasting.
- No production deployment.
- No global session cleanup (only owner-declared).
- No fabricated test counts, SHAs, or product readiness claims.

## Forward references

G01 implementation map: see `G01_IMPLEMENTATION_MAP.md`.
AADS v1.2 blocker: see `AADS_BLOCKER.md`.

---

## G01 — Capability Registry (added 2026-10-19)

### New layer
```
backend/src/manara/
├── registry/                   # NEW (G01)
│   ├── __init__.py
│   ├── embeddings.py           # Embedder + NumpyEmbeddingStore + PgvectorEmbeddingStore
│   ├── converters.py           # Pydantic ↔ ORM conversion
│   ├── service.py              # CapabilityRegistry — the 5-stage retrieval pipeline
│   └── seed_cards.py           # 8 high-quality seed capability cards
├── db/
│   ├── models.py               # G00: InvestigationRow
│   └── registry_models.py     # NEW (G01): 7 ORM models for the registry
└── api/routes/
    ├── status.py               # G00 (+ G01 capability list)
    ├── discovery.py            # G00
    ├── contracts.py            # G00
    └── registry.py             # NEW (G01): 12 endpoints
```

### Retrieval pipeline (per `01_ARCHITECTURE/02_CONTRACTS.md` §Retrieval strategy)

| Stage | Purpose | Implementation |
|-------|---------|----------------|
| 1_filter | tenant + status + domain/tag/language filters | SQLAlchemy query |
| 2_hybrid | text similarity (token overlap, multilingual) + semantic similarity (MiniLM cosine) | numpy + EmbeddingStore |
| 3_rerank | positive-example boost + negative-example penalty | EmbeddingStore search by kind |
| 4_validate | ensure status is searchable | done in stage 1 |
| 5_return | top-k with reasons + gap analysis | list slice + gap notes |

### Embedding model

* **Model**: `paraphrase-multilingual-MiniLM-L12-v2`
* **Dimension**: 384
* **Multilingual**: handles Arabic + English queries symmetrically
* **Production store**: PostgreSQL + pgvector (ivfflat index, cosine ops)
* **Dev/test store**: SQLite + JSON column + numpy cosine (identical algorithm)
* **Pinned metadata**: every embedding row stores `model_name`, `model_version`, `embedding_dim` — so future model swaps can detect and re-encode stale vectors

### Eight seed capability cards

| Card ID | Domain coverage |
|---------|-----------------|
| search.academic-publications | academic, research, science |
| search.patent-intelligence | industry, batteries, medicine, robotics, construction |
| search.clinical-trials | medicine, health, biomedical, regulatory |
| search.energy-ev-datasets | energy, automotive, manufacturing, supply-chain |
| search.agricultural-statistics | agriculture, food, climate, trade |
| search.geopolitical-events | geopolitics, events, media, conflict |
| search.waste-recycling-statistics | waste, recycling, environment, policy |
| search.github-activity | technology, open-source, ai, software |

All 8 cards ship with:
* 15–30 positive examples (per spec requirement)
* 3+ mandatory negative examples (per spec requirement)
* Multilingual keywords (ar + en)
* Status = `candidate` (NOT approved; owner-promotion required)
* Empty `connector_ids` (real connectors arrive in G02)
