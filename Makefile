# MANARA — Makefile
# Convenience commands. Each target is idempotent and self-documenting.

PYTHON ?= python3
PIP ?= pip

.PHONY: help setup backend-dev backend-test backend-lint backend-migrate \
        frontend-dev frontend-build frontend-typecheck \
        test docker-up docker-down clean

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup:  ## Create Python venv + install backend deps + install frontend deps
	cd backend && $(PYTHON) -m venv .venv && . .venv/bin/activate && $(PIP) install -e ".[dev]"
	cd frontend && npm install

backend-migrate:  ## Apply Alembic migrations
	cd backend && . .venv/bin/activate && manara-migrate

backend-dev:  ## Start uvicorn with reload (port 8000)
	cd backend && . .venv/bin/activate && uvicorn manara.app:create_app --factory --reload --port 8000

backend-test:  ## Run pytest
	cd backend && . .venv/bin/activate && pytest -v

backend-lint:  ## Run ruff + mypy
	cd backend && . .venv/bin/activate && ruff check . && mypy src/manara

frontend-dev:  ## Start Vite dev server (port 5173)
	cd frontend && npm run dev

frontend-build:  ## Production build
	cd frontend && npm run build

frontend-typecheck:  ## tsc --noEmit
	cd frontend && npm run typecheck

test: backend-test frontend-typecheck  ## Run all tests

docker-up:  ## Start dev compose stack (NOT tested in G00 sandbox)
	docker compose up

docker-down:  ## Stop dev compose stack
	docker compose down

clean:  ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +
	find . -type d -name dist -exec rm -rf {} +
	rm -f backend/*.db backend/manara_dev.db
