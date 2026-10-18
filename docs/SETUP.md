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
