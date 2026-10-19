# MANARA — Staging Readiness Guide

> **MANARA Foundation v1.0 · 2026-10-19 · Staging Deployment**
> Code: https://github.com/mayakilzy/AgentCraft-MANARA (commit: latest on main)
> Tag: `v1.0.0-acceptance`

## 1. Prerequisites

### Required on the Staging machine:
- Docker ≥ 24 + Docker Compose
- Git

### Optional (for live features):
- Z.AI API key (for live LLM via GLM)
- OpenAlex API key (for reliable search)

## 2. Deployment Steps

```bash
# 1. Clone the repository
git clone https://github.com/mayakilzy/AgentCraft-MANARA.git
cd AgentCraft-MANARA

# 2. Create .env file
cp .env.example .env
# Edit .env:
#   DATABASE_URL=postgresql+psycopg://manara:CHANGE_ME_IN_STAGING@postgres:5432/manara
#   MANARA_ENV=staging
#   MANARA_SINGLE_TENANT_DEMO=true

# 3. (Optional) Set API keys for live features
# Add to .env or docker-compose.yml environment section:
#   MANARA_ZAI_API_KEY=your-zai-key
#   MANARA_OPENALEX_API_KEY=your-openalex-key

# 4. Start all services
docker compose up -d

# 5. Wait for PostgreSQL to be healthy
docker compose ps  # postgres should show "healthy"

# 6. Apply database migrations (auto-run in backend command, but verify)
docker compose exec backend alembic upgrade head

# 7. Seed initial capability cards (8 cards from G01)
curl -X POST http://localhost:8000/registry/capabilities/seed

# 8. Verify the application is running
curl http://localhost:8000/status | python3 -m json.tool
# Frontend: http://localhost:5173
```

## 3. Testing the Investigation Journey

### Manual Test (Browser)

1. Open `http://localhost:5173` in your browser
2. Enter a research question (e.g., "Future of waste recycling technologies")
3. Click "حلّل وابني القالب · Compose Mold"
4. Wait for the analysis result (model loading may take ~30s on first run)
5. Verify:
   - A real `investigation_id` (inv-xxx) appears
   - Detected needs are listed
   - Coverage levels shown (catalog/operational)
   - Gaps are displayed
   - Deliverable type is shown
6. Click "متابعة في مساحة التحقيق · Open in Workspace"
7. In Workspace, click "إنشاء تقرير · Create Dossier"
8. Verify the publication appears with quality gate result
9. If downloadable, click the Markdown download link
10. Refresh the page — investigation context should persist

### Automated Test (Playwright)

```bash
# Install Playwright
pip install playwright
playwright install chromium

# Run the staging E2E test
python tests/e2e/test_staging_journey.py
```

Expected output: 9 tests, screenshot saved to `tests/e2e/screenshot_staging.png`

## 4. Backup & Restore

### Backup

```bash
# Database
docker compose exec postgres pg_dump -U manara manara > backup_$(date +%Y%m%d).sql

# Object storage (snapshots)
docker compose run --rm -v $(pwd)/backups:/backup backend \
  tar czf /backup/snapshots_$(date +%Y%m%d).tar.gz /app/var/snapshots/
```

### Restore

```bash
# Database
docker compose exec -T postgres psql -U manara manara < backup_20261019.sql

# Object storage
docker compose run --rm -v $(pwd)/backups:/backup backend \
  tar xzf /backup/snapshots_20261019.tar.gz -C /
```

## 5. Rollback

```bash
# 1. Stop services
docker compose down

# 2. Revert to previous commit
git checkout <previous-stable-commit>

# 3. Restore database if needed
docker compose exec -T postgres psql -U manara manara < backup.sql

# 4. Rebuild and restart
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## 6. Service Recovery

```bash
# Check logs
docker compose logs backend --tail 50
docker compose logs frontend --tail 50
docker compose logs postgres --tail 50

# Restart a single service
docker compose restart backend

# Re-run migrations
docker compose exec backend alembic upgrade head

# Check health
curl http://localhost:8000/health
curl -o /dev/null -w "%{http_code}" http://localhost:5173
```

## 7. Known Constraints (honestly documented)

| Constraint | Impact | Resolution |
|------------|--------|------------|
| Playwright not tested | Browser E2E unverified | Run on Staging |
| Live LLM not tested | Agent mock only | Set MANARA_ZAI_API_KEY |
| OpenAlex search rate-limited | Shared IP budget | Set MANARA_OPENALEX_API_KEY |
| PostgreSQL + pgvector untested | SQLite only in tests | Docker Compose uses pgvector/pgvector:pg16 |
| Multi-tenant auth not implemented | Single-tenant demo | Future enhancement |
| No SSL/TLS | Nginx config needed | Add reverse proxy with TLS |

## 8. What to Look For in Staging

Per owner (G09-R1):
> "أول يوم يفتح فيه الدكان للزبائن التجريبيين هو الاختبار الذي سيحدد
> إن كانت منارة تحقق الرؤية التي بدأنا من أجلها."

Watch for:
1. Does the question → mold → publication journey work from the browser?
2. Are the coverage levels (catalog vs operational) displayed correctly?
3. Are gaps honestly reported (not hidden)?
4. Does the download produce a real, non-empty file?
5. Does page refresh preserve the investigation context?
6. Does Arabic RTL display correctly?
7. Does English LTR display correctly?
8. Are empty states honest ("no data yet")?
