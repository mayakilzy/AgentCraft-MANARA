# Setup Guide

> **MANARA G00 · local setup**

## Prerequisites

- Python ≥ 3.12
- Node.js ≥ 20 (tested with v24)
- npm ≥ 10
- Git ≥ 2.40
- (optional, for PostgreSQL target) Docker ≥ 24, or a local PostgreSQL 16 instance
- (optional) `make` for convenience targets

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env      # edit if you want different ports / Postgres

# Apply migrations (creates ./manara_dev.db by default)
manara-migrate

# Start the API (default port 8000, hot reload)
uvicorn manara.app:create_app --factory --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/status | python3 -m json.tool
curl http://localhost:8000/discovery | python3 -m json.tool
curl http://localhost:8000/contracts/schemas | python3 -m json.tool
```

OpenAPI docs at http://localhost:8000/docs

## Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The Vite dev server proxies `/status`, `/health`, `/discovery`, `/contracts` to
the backend, so the frontend just works once the backend is up.

## Tests

```bash
cd backend
source .venv/bin/activate

# Unit + contract + e2e smoke
pytest -v

# Coverage
pytest --cov=manara --cov-report=term-missing

# Lint + typecheck
ruff check .
mypy src/manara
```

```bash
cd frontend
npm run typecheck    # tsc --noEmit
```

## PostgreSQL target (when ready)

Switch the dev variant to PostgreSQL by editing `.env`:

```
DATABASE_URL=postgresql+psycopg://manara:CHANGE_ME@localhost:5432/manara
```

Either install PostgreSQL locally and create the database/user, or use the
provided `docker-compose.yml`:

```bash
docker compose up postgres   # start just PG
# from backend venv:
manara-migrate               # apply migrations to PG
```

⚠️ The `docker-compose.yml` is provided for environments that have Docker.
**It was NOT tested in the G00 sandbox** because Docker is not available
here. See `AADS_BLOCKER.md` for details.

## Common pitfalls

1. **"No module named manara"** — make sure you ran `pip install -e ".[dev]"`
   from the `backend/` directory (the `-e` editable install puts `src/manara`
   on `sys.path`).

2. **Pydantic import errors** — the project requires Pydantic v2. The
   `pyproject.toml` pins `pydantic>=2.9,<3`.

3. **`AttributeError: 'NoneType' object has no attribute 'engine'`** — if you
   swapped `DATABASE_URL` after the engine was created, call
   `manara.db.session.reset_engine()` (or restart the process).

4. **CORS errors in the browser** — make sure the backend is running and
   `MANARA_PORT` matches the proxy target in `frontend/vite.config.ts`
   (default 8000).

5. **Alembic complains about empty migrations dir** — the migrations live at
   `backend/alembic/versions/0001_initial.py`. If you don't see them, you
   likely cloned a partial tree; re-run `git checkout main` from the repo
   root.

---

## G01 — Additional setup (embeddings model)

G01 introduces the MiniLM embedding model. The first time you run any
registry test or boot the API with the registry router enabled, the model
is downloaded (~120MB) and cached.

### Set the cache location

```bash
export SENTENCE_TRANSFORMERS_HOME=/home/z/my-project/.models
export HF_HOME=/home/z/my-project/.models/hf_cache
```

(These are set automatically by `tests/conftest.py` for tests, but you
should set them in your shell for `uvicorn` and `manara-migrate`.)

### Running the acceptance evidence script

After applying migrations and starting the API once (so tables exist),
you can run the standalone acceptance evidence script to see the
prosthetics test live:

```bash
cd /home/z/my-project/repos/AgentCraft-MANARA
DATABASE_URL="sqlite:///./manara_dev.db" \
SENTENCE_TRANSFORMERS_HOME=/home/z/my-project/.models \
HF_HOME=/home/z/my-project/.models/hf_cache \
python3 scripts/g01_acceptance_evidence.py
```

The script:
1. Creates a fresh SQLite DB at `/tmp/manara_g01_evidence.db`
2. Seeds all 8 capability cards (auto-generates ~240 embeddings)
3. Runs the prosthetics query, the Arabic query, the battery query, and
   the negative-example reranker test
4. Prints real scores and reasons
5. Cleans up

### Frontend with registry browser

After running both backend and frontend dev servers:

```bash
# Terminal 1
cd backend && uvicorn manara.app:create_app --factory --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

Open http://localhost:5173 and:
1. Click "تحميل 8 بطاقات أولية" to seed the cards
2. Click "بحث" to run the prosthetics query (pre-filled in the search bar)
3. Click any card in the list to see full details + positive/negative examples
4. Use the "اعتماد" / "رفض" buttons to promote or reject (owner approval flow)
