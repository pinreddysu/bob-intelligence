# Bob Intelligence — convenience targets
# Usage: make <target>

.PHONY: help setup install install-dev dev-backend dev-frontend \
        test test-v test-file test-cov smoke \
        docker-up docker-down docker-down-clean docker-build \
        lint format clean

# ── Default ───────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Bob Intelligence — available targets"
	@echo "────────────────────────────────────────────────────────────"
	@echo "  setup          Copy .env.example → backend/.env (first-time setup)"
	@echo "  install        Install backend runtime dependencies"
	@echo "  install-dev    Install backend runtime + dev dependencies"
	@echo "  dev-backend    Start FastAPI dev server (hot reload, :8000)"
	@echo "  dev-frontend   Install frontend deps and start Vite dev server (:5173)"
	@echo ""
	@echo "  test           Run full pytest suite"
	@echo "  test-v         Run pytest with verbose output"
	@echo "  test-cov       Run pytest with coverage report"
	@echo "  smoke          Run end-to-end smoke test against localhost:8000"
	@echo ""
	@echo "  docker-build        Build Docker images (no cache)"
	@echo "  docker-up           Build and start all services with Docker Compose"
	@echo "  docker-down         Stop containers (keep db_data volume)"
	@echo "  docker-down-clean   Stop containers AND delete db_data volume"
	@echo ""
	@echo "  clean          Remove __pycache__, .pyc files, and test DB"
	@echo "────────────────────────────────────────────────────────────"
	@echo ""

# ── First-time setup ──────────────────────────────────────────────────────────

setup:
	@if [ -f backend/.env ]; then \
	  echo "backend/.env already exists — skipping. Edit it directly if needed."; \
	else \
	  cp backend/.env.example backend/.env; \
	  echo "Created backend/.env from .env.example — fill in your values before starting."; \
	fi

# ── Python setup ──────────────────────────────────────────────────────────────

install:
	pip install -r backend/requirements.txt

install-dev:
	pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# ── Local dev servers ─────────────────────────────────────────────────────────

dev-backend:
	uvicorn backend.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	pytest

test-v:
	pytest -v

test-cov:
	pytest --cov=backend --cov-report=term-missing

# Run a specific test file: make test-file FILE=backend/tests/test_milestone2.py
test-file:
	pytest $(FILE) -v

smoke:
	bash scripts/smoke_test.sh

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker compose build --no-cache

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-down-clean:
	docker compose down -v

# ── Housekeeping ──────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f backend/bob_intelligence_test.db
