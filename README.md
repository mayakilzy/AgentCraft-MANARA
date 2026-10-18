MANARA — Adaptive Intelligence Factory
=====================================

> **MANARA Foundation v1.0 · G00 Engineering Foundation**
> Owner: Ayman · Supervisor: ChatGPT · Implementer: GLM
> Code repository: https://github.com/mayakilzy/AgentCraft-MANARA
> Specifications: https://github.com/mayakilzy/repo-info/tree/main/AgentCraft-MANARA

MANARA is a sector-agnostic adaptive intelligence research factory. It transforms an
investigation question into discoverable sources, validated search capabilities,
evidence-backed structured knowledge, calibrated forecasting when justified, and
publishable research and visual products. **G00 only delivers the engineering
foundation — typed contracts, minimal scaffold, smoke tests, and an explicitly
synthetic discovery view. It does not implement real search or forecasting.**

---

## Status (G00)

| Aspect                       | Status                                                       |
|------------------------------|--------------------------------------------------------------|
| Typed contracts (8)          | Implemented as Pydantic v2 models + JSON Schema              |
| API surface                  | `/status`, `/discovery` (synthetic), `/health`, error handlers |
| Frontend                     | Vite + React + TypeScript shell, status + synthetic discovery |
| Persistence                  | SQLAlchemy 2.x + Alembic; SQLite dev variant; PostgreSQL production target |
| Docker Compose               | Provided for PG + backend + frontend; NOT tested here (Docker unavailable in this sandbox) |
| Tests                        | Contract, schema, API smoke, error handling, end-to-end smoke |
| Lint / Typecheck             | ruff + mypy (backend); tsc --noEmit (frontend)              |
| Secrets policy               | `.env.example` only; no tokens committed; public ZIPs forbidden |
| AADS v1.2 inspection         | BLOCKER — see `docs/AADS_BLOCKER.md`                         |

---

## Repository layout

```
AgentCraft-MANARA/
├── backend/                  # FastAPI + Pydantic + SQLAlchemy + Alembic
│   ├── src/manara/
│   │   ├── api/              # Routes: status, discovery, errors
│   │   ├── contracts/        # 8 typed contracts (Pydantic v2)
│   │   ├── db/               # SQLAlchemy models + session
│   │   └── lifecycle/        # State enums for Foundry/Mold/Agent/Investigation
│   ├── tests/                # Contract + API + e2e smoke tests
│   └── pyproject.toml
├── frontend/                 # Vite + React + TypeScript shell
├── docs/                     # Architecture, setup, G01 map, AADS blocker, licenses
├── docker-compose.yml        # Postgres + backend + frontend (NOT tested locally)
├── Makefile                  # Convenience commands
└── .env.example              # No secrets, only placeholders
```

---

## Quick start (development, no Docker required)

1. **Backend**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   cp ../.env.example ../.env           # Edit if you need different ports
   manara-migrate                       # Apply SQLite migrations
   uvicorn manara.app:create_app --factory --reload --port 8000
   ```
   Visit: http://localhost:8000/status  ·  http://localhost:8000/discovery

2. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Visit: http://localhost:5173

3. **Tests**
   ```bash
   cd backend
   pytest -v                            # unit + contract + e2e smoke
   ruff check . && mypy src/manara      # lint + typecheck
   cd ../frontend && npm run typecheck  # tsc --noEmit
   ```

See `docs/SETUP.md` for the full guide, `docs/ARCHITECTURE.md` for the
code-to-spec mapping, and `docs/G01_IMPLEMENTATION_MAP.md` for the next
mission's plan.

---

## What G00 is NOT

Per the G00 mission and the project's *negative requirements*:

- It is **not** a working intelligence factory.
- It does **not** perform real source discovery, search, or forecasting.
- It contains **no** real connector, no real source call, no real evidence.
- The `/discovery` view is **explicitly labeled synthetic** and exists only
  to validate the API contract end-to-end.
- It does **not** push to production or activate generated code.

---

## Security notes

- No credentials are committed. `.env.example` contains only placeholders.
- `repo-info/START-HERE/GeneralGH.zip` is **not** an approved credential source
  and must not be loaded. Rotate any real tokens that may have been placed
  there.
- Tenant isolation is *architected* (every contract carries `tenant_id`) but
  *enforcement* is deferred to G03 per the roadmap.

---

## License

To be selected by the owner. Default placeholder: MIT-compatible for the
foundation scaffold; downstream integrations must respect each connector's
license (see `docs/LICENSES.md`).
