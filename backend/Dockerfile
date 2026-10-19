# MANARA backend image — Staging-ready.
# Includes: Python 3.12, psycopg, sentence-transformers, pgvector, alembic.

FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg, build tools, and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY README.md ./
RUN pip install --no-cache-dir -e ".[postgres,dev]"

# Create directories for models and snapshots
RUN mkdir -p /app/.models /app/.models/hf_cache /app/var/snapshots

EXPOSE 8000
CMD ["uvicorn", "manara.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
