# MANARA — Staging Readiness Guide

> **MANARA Foundation v1.0 · 2026-10-19 · Staging Deployment**
> Code: https://github.com/mayakilzy/AgentCraft-MANARA (latest on main)

## 1. Prerequisites

- Docker ≥ 24 + Docker Compose
- Git
- (Optional) Z.AI API key for live LLM
- (Optional) OpenAlex API key for reliable search

## 2. Deployment Steps

```bash
# 1. Clone
git clone https://github.com/mayakilzy/AgentCraft-MANARA.git
cd AgentCraft-MANARA

# 2. Create .env file
cp .env.example .env
# Edit .env — MUST change POSTGRES_PASSWORD

# 3. Start all services (PostgreSQL + Backend + Frontend)
docker compose up -d

# 4. Wait for PostgreSQL health
docker compose ps
# postgres should show "healthy"

# 5. Verify backend started (migrations auto-run in the command)
docker compose logs backend --tail 20
# Should see: "alembic upgrade head" + "Uvicorn running"

# 6. Seed capability cards
curl -X POST http://localhost:8000/registry/capabilities/seed

# 7. Verify
curl http://localhost:8000/status | python3 -m json.tool
```

Access:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 3. Docker Compose Configuration

The `docker-compose.yml` uses `${VAR:-default}` syntax for all env vars.
Values come from `.env` file (which you create from `.env.example`).

### Key env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | manara | DB user |
| `POSTGRES_PASSWORD` | CHANGE_ME_IN_STAGING | **MUST change** |
| `POSTGRES_DB` | manara | DB name |
| `MANARA_ENV` | staging | Runtime mode |
| `MANARA_ZAI_API_KEY` | (empty) | Z.AI LLM key |
| `MANARA_OPENALEX_API_KEY` | (empty) | OpenAlex API key |

### Networking:

- Frontend container uses `VITE_API_TARGET=http://backend:8000` to proxy
  API requests to the backend container via Docker's internal network.
- In local dev (outside Docker), `VITE_API_TARGET` defaults to
  `http://localhost:8000`.
- All 11 API route prefixes are proxied: `/status`, `/health`, `/discovery`,
  `/contracts`, `/registry`, `/foundry`, `/memory`, `/mold-factory`,
  `/agents`, `/foresight`, `/publishing`.

### Verify configuration:

```bash
# Check resolved env vars
docker compose config

# Check service health
docker compose ps
```

## 4. Browser E2E Test

```bash
# Install Playwright
pip install playwright
playwright install chromium

# Run the strict acceptance test (11 tests)
python tests/e2e/test_staging_journey.py
```

### What the test verifies (STRICT — no soft passes):

1. Homepage loads with textarea
2. Status API returns 200 with MANARA
3. Compose API returns real investigation_id (inv-xxx, NOT null)
4. Mold has detected_needs, is_complete, deliverable_type
5. UI compose: question → Analysis Result visible
6. investigation_id (inv-xxx) appears in UI text
7. Publication created with real investigation_id (NOT inv-session)
8. Download produces non-empty file with correct content
9. No critical JavaScript errors (Uncaught, TypeError)
10. Investigation context preserved after page refresh
11. Screenshot saved

Result codes: 0 = ALL PASS, 1 = AT LEAST ONE FAIL, 2 = SKIPPED

## 5. Manual Browser Test Checklist

1. Open http://localhost:5173
2. Enter: "Future of waste recycling technologies in the next ten years"
3. Click "حلّل وابني القالب"
4. Verify:
   - Real investigation_id (inv-xxx) appears
   - Detected needs listed
   - Coverage levels shown (catalog/operational)
   - Gaps displayed
   - Deliverable type shown
5. Click "متابعة في مساحة التحقيق"
6. In Workspace, click "إنشاء تقرير"
7. Verify publication + quality gate result
8. Click download link — file must be non-empty
9. Refresh page — context must persist
10. Check Arabic RTL and English LTR display

## 6. Backup & Restore

```bash
# Backup
docker compose exec postgres pg_dump -U manara manara > backup_$(date +%Y%m%d).sql

# Restore
docker compose down
docker compose up -d postgres
docker compose exec -T postgres psql -U manara manara < backup_20261019.sql
docker compose up -d
```

## 7. Rollback

```bash
docker compose down
git checkout <previous-commit>
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## 8. Known Constraints

| Constraint | Status | Resolution |
|------------|--------|------------|
| Docker build not tested | NOT TESTED | Run on Staging |
| Playwright not tested | NOT TESTED | Run on Staging |
| Live LLM | NOT TESTED | Set MANARA_ZAI_API_KEY |
| OpenAlex search | NOT TESTED | Set MANARA_OPENALEX_API_KEY |
| Multi-tenant auth | NOT IMPLEMENTED | Single-tenant demo mode |
| No SSL/TLS | NOT CONFIGURED | Add Nginx reverse proxy |
