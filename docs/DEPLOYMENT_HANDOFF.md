# G09 Deployment Handoff Guide

> **MANARA Foundation v1.0 · 2026-10-19 · Deployment & Operations**
> Owner: Ayman · Implementer: GLM

## 1. Prerequisites

### Required Software
- Docker ≥ 24 + Docker Compose
- Python 3.12+
- Node.js 20+ (for frontend build)
- PostgreSQL 16 + pgvector extension (for production)

### Required Credentials (via secrets manager — NEVER in code)
- `MANARA_ZAI_API_KEY` — for live LLM execution (Z.AI/GLM)
- `MANARA_OPENALEX_API_KEY` — for reliable OpenAlex search (optional but recommended)
- `MANARA_S3_BUCKET` + AWS creds — for object storage in production
- Database password (PostgreSQL)

## 2. Docker Compose Deployment

### Quick Start (Development)

```bash
# Clone the repository
git clone https://github.com/mayakilzy/AgentCraft-MANARA.git
cd AgentCraft-MANARA

# Copy env example
cp .env.example .env
# Edit .env with your settings

# Start all services
docker compose up -d

# Apply database migrations
docker compose exec backend alembic upgrade head

# Seed initial capability cards
curl -X POST http://localhost:8000/registry/capabilities/seed

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Production Deployment

```bash
# 1. Set production environment variables
export MANARA_ENV=production
export DATABASE_URL=postgresql+psycopg://manara:CHANGE_ME@postgres:5432/manara
export MANARA_ZAI_API_KEY=your_key_here
export MANARA_OPENALEX_API_KEY=your_key_here

# 2. Build and start
docker compose -f docker-compose.prod.yml up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Verify health
curl http://localhost:8000/status | python -m json.tool
```

## 3. Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name manara.example.com;

    # Frontend
    location / {
        proxy_pass http://frontend:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Direct API access (without /api prefix)
    location ~ ^/(status|health|discovery|contracts|registry|foundry|memory|mold-factory|agents|foresight|publishing) {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 4. Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Expected response:
# {"app": "MANARA", "version": "0.1.0", "env": "production", ...}

# Frontend health (should return HTML)
curl -o /dev/null -w "%{http_code}" http://localhost:5173
# Expected: 200
```

## 5. Backup & Restore

### Database Backup

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U manara manara > backup_$(date +%Y%m%d).sql

# Backup object storage (if using local FS)
tar czf snapshots_backup_$(date +%Y%m%d).tar.gz var/snapshots/
```

### Database Restore

```bash
# Restore PostgreSQL
docker compose exec -T postgres psql -U manara manara < backup_20261019.sql

# Restore object storage
tar xzf snapshots_backup_20261019.tar.gz
```

## 6. Rollback Procedure

```bash
# 1. Stop services
docker compose down

# 2. Revert to previous image/tag
git checkout <previous-stable-commit>
docker compose build

# 3. Restore database (if migrations changed schema)
docker compose exec -T postgres psql -U manara manara < backup_before_update.sql

# 4. Restart
docker compose up -d

# 5. Verify
curl http://localhost:8000/status
```

## 7. Update Procedure

```bash
# 1. Pull latest code
git pull origin main

# 2. Build new images
docker compose build

# 3. Backup database (safety)
docker compose exec postgres pg_dump -U manara manara > pre_update_backup.sql

# 4. Apply migrations
docker compose exec backend alembic upgrade head

# 5. Restart services
docker compose up -d

# 6. Verify
curl http://localhost:8000/status | python -m json.tool
```

## 8. Service Recovery After Failure

```bash
# If backend fails to start:
# 1. Check logs
docker compose logs backend --tail 50

# 2. Check database connectivity
docker compose exec backend python -c "from manara.db.session import get_engine; e = get_engine(); print(e.url)"

# 3. Re-run migrations
docker compose exec backend alembic upgrade head

# If frontend fails to start:
# 1. Check if node_modules exist
docker compose exec frontend ls node_modules | head -5

# 2. Rebuild
docker compose exec frontend npm install
docker compose exec frontend npm run build

# If PostgreSQL fails:
# 1. Check data volume
docker volume ls | grep pgdata
# 2. If corrupt, restore from backup
docker compose exec -T postgres psql -U manara manara < backup.sql
```

## 9. Monitoring

### Key metrics to monitor:
- Backend response time (< 500ms for /status)
- Database connection pool usage
- Frontend bundle size
- Memory usage of MiniLM model (~120MB)
- Disk usage of object storage (var/snapshots/)

### Log locations:
- Backend: `docker compose logs backend`
- Frontend: `docker compose logs frontend`
- Database: `docker compose logs postgres`

## 10. Known Constraints

1. **Live LLM not tested**: MockProvider used in all tests. ZAIProvider requires `MANARA_ZAI_API_KEY`.
2. **OpenAlex search rate-limited**: shared IP budget may exhaust. API key recommended.
3. **PostgreSQL + pgvector not tested in sandbox**: SQLite used for all tests.
4. **Playwright browser tests not executed**: no browser available in sandbox.
5. **Multi-tenant auth not implemented**: single-tenant demo mode only.
6. **No SSL/TLS configured**: Nginx config assumes a reverse proxy handles TLS.
