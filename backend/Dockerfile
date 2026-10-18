# MANARA backend image — DEVELOPMENT ONLY.
# G00 does NOT ship a production-grade Dockerfile.

FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg and build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY README.md ./
RUN pip install --no-cache-dir -e ".[postgres,dev]"

EXPOSE 8000
CMD ["uvicorn", "manara.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
