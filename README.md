# Bob Intelligence

An explainable recommendation system that helps engineering teams decide **which Jira story to work on next** and **how to execute it** (Bob-led, Collaborative, or Human-led), backed by historical evidence from resolved tickets, PR analysis, and an LLM.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
  - [Backend](#backend)
  - [Frontend](#frontend)
- [Environment Variables](#environment-variables)
- [Docker Deployment](#docker-deployment)
- [API Reference](#api-reference)
- [Testing](#testing)
  - [Unit & Integration Tests (pytest)](#unit--integration-tests-pytest)
  - [Smoke Test (end-to-end shell)](#smoke-test-end-to-end-shell)
- [LLM Provider Configuration](#llm-provider-configuration)
- [Jira Integration](#jira-integration)
- [GitHub PR Enrichment](#github-pr-enrichment)

---

## Overview

Bob Intelligence is a single-user, wizard-style decision-support tool with four screens:

1. **Story Selector** — import stories from Jira or sample data; view priority ranking.
2. **Recommendation View** — execution-mode recommendation (Bob-led / Collaborative / Human-led) with supporting evidence, similar historical tickets, PR links, and LLM rationale. A tech lead must approve or override before work begins.
3. **Link Bob Work** — attach a Bob session to the approved story.
4. **Outcome & Comparison** — record acceptance-criteria outcomes and compare against the recommendation.

Recommendations are fully explainable: every signal is surfaced with its source, confidence level, and uncertainty note. No evidence is invented and the system never silently substitutes sample data for a failed live integration.

---

## Architecture

```
Browser (React 19 / Vite)
      │  REST JSON (proxied /api/*)
      ▼
FastAPI 0.115  (Python 3.11+)
      ├── /api/stories              ──► jira_service  ──► Jira REST v3 / sample data
      ├── /api/recommendations      ──► recommendation_service
      │                                   ├── priority_engine
      │                                   ├── historical_evidence_service  (TF-IDF similarity)
      │                                   │     └── github_service         (PR evidence)
      │                                   └── llm_service                  (IBM Bob / OpenAI / watsonx)
      ├── /api/resolved-tickets     ──► Jira resolved-ticket history / sample data
      ├── /api/bob-sessions         ──► SQLite
      └── /api/outcomes             ──► SQLite
              │
        SQLAlchemy 2.0
              │
        SQLite (bob_intelligence.db)
```

**Tech stack:**
| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI 0.115, SQLAlchemy 2.0, Pydantic v2 |
| Database | SQLite (file-backed; swap to PostgreSQL via `DATABASE_URL`) |
| Frontend | React 19, TypeScript 5, Vite 6, React Router 7 |
| Container | Docker (multi-stage builds), nginx 1.27, Docker Compose |
| LLM | IBM Bob CLI (default), OpenAI, IBM watsonx.ai |
| Testing | pytest 8, pytest-asyncio, FastAPI TestClient |

---

## Repository Structure

```
bob-intelligence/
├── backend/
│   ├── main.py                        # FastAPI app entry point (v0.4.0)
│   ├── database.py                    # SQLAlchemy engine + session
│   ├── models.py                      # ORM models
│   ├── schemas.py                     # Pydantic request/response schemas
│   ├── routers/
│   │   ├── stories.py                 # GET/POST /api/stories
│   │   ├── recommendations.py         # POST/GET/PATCH /api/recommendations
│   │   ├── resolved_tickets.py        # POST/GET /api/resolved-tickets
│   │   ├── bob_sessions.py            # POST /api/bob-sessions
│   │   └── outcomes.py               # POST /api/outcomes
│   ├── services/
│   │   ├── jira_service.py            # Jira REST v3 client + sample fallback
│   │   ├── recommendation_service.py  # Rule engine: priority + execution mode
│   │   ├── historical_evidence_service.py  # TF-IDF similarity search
│   │   ├── github_service.py          # GitHub API: PR diff + metadata
│   │   ├── llm_service.py             # LLM abstraction (Bob/OpenAI/watsonx)
│   │   └── evidence_service.py        # Git diff / test-result capture
│   ├── sample_data/
│   │   ├── stories.json
│   │   ├── resolved_tickets.json
│   │   └── developer_profiles.json
│   ├── tests/                         # pytest test suite
│   ├── conftest.py                    # Fixtures: isolated test DB, LLM stub
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                     # StorySelector, RecommendationView, …
│   │   ├── components/                # AppShell, ApprovalPanel, ui.tsx
│   │   └── api/                       # Typed fetch wrappers + response types
│   ├── nginx.conf                     # Reverse-proxy template (envsubst)
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── .env.example
├── scripts/
│   └── smoke_test.sh                  # Milestone 4a end-to-end smoke test
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Python | 3.11 | 3.14 confirmed working |
| Node.js | 20 LTS | 20–26 all work |
| npm | 10+ | ships with Node |
| Docker | 24+ | for containerised deployment |
| Docker Compose | v2 (`docker compose`) | plugin bundled with Docker Desktop |
| IBM Bob CLI | latest | required only when `LLM_PROVIDER=bob` |

---

## Local Development Setup

### Backend

```bash
# 1. Clone and enter the repo
git clone <repo-url> bob-intelligence
cd bob-intelligence

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install runtime + dev dependencies
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# 4. Configure environment variables (or: make setup)
cp backend/.env.example backend/.env
# Edit backend/.env — minimum required for local dev with sample data:
#   LLM_PROVIDER=bob
#   LLM_API_KEY=<your-bob-api-key>
# Leave JIRA_* and GITHUB_TOKEN blank to use sample data.

# 5. Start the FastAPI server
uvicorn backend.main:app --reload --port 8000
```
> **First run:** on startup the backend automatically seeds sample resolved tickets into the DB if the table is empty — no manual import step needed.

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### Frontend

```bash
# In a separate terminal, from the repo root:
cd frontend

# 1. Install dependencies
npm install

# 2. (Optional) create a local env override
cp .env.example .env.local
# Vite proxies /api/* to localhost:8000 by default — no changes needed for local dev.

# 3. Start the dev server
npm run dev
```

The UI is now available at `http://localhost:5173`.

---

## Environment Variables

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in the values you need.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | in-memory SQLite | `sqlite:///./bob_intelligence.db` for file persistence; PostgreSQL URL for production |
| `JIRA_BASE_URL` | For Jira import | — | `https://yourorg.atlassian.net` |
| `JIRA_USER_EMAIL` | For Jira import | — | Atlassian account email |
| `JIRA_API_TOKEN` | For Jira import | — | [Generate here](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `JIRA_STORY_POINTS_FIELD` | No | `customfield_10016` | Custom field key for story points |
| `JIRA_AC_FIELD` | No | — | Custom field key for acceptance criteria |
| `GITHUB_TOKEN` | For private repos | — | PAT with `repo` read scope |
| `LLM_PROVIDER` | No | `bob` | `bob` \| `openai` \| `watsonx` |
| `LLM_API_KEY` | For LLM | — | API key for the selected provider |
| `BOB_API_KEY` | For `bob` provider | — | Same as `LLM_API_KEY` for Bob CLI |
| `LLM_ENDPOINT` | For watsonx | — | e.g. `https://us-south.ml.cloud.ibm.com` |
| `LLM_MODEL` | No | provider default | Model identifier |
| `LLM_PROJECT_ID` | For watsonx | — | watsonx project ID |
| `PIE_REPO_PATH` | No | — | Absolute path to local PIE repo clone (future milestone) |

> **Note:** When `LLM_API_KEY` is absent the mode recommendation defaults to `"collaborative"` and the `uncertainty_note` is explicitly labelled as not evidence-based.

### Frontend (`frontend/.env.local`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Production only | _(empty)_ | Backend origin without trailing slash, e.g. `https://api.example.com`. Leave blank in development — Vite proxies `/api/*` automatically. |

---

## Docker Deployment

### Quick start (single command)

```bash
# 1. Create the backend env file (or: make setup)
cp backend/.env.example backend/.env
# Edit backend/.env with your real values

# 2. Build and start both services
docker compose up --build
```
> The backend exposes `GET /api/health` and Docker Compose waits for it to return 200 before starting the frontend container.

| Service | URL |
|---|---|
| Frontend (nginx) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

### Stopping

```bash
docker compose down          # stop containers, keep db_data volume  (or: make docker-down)
docker compose down -v       # stop containers AND delete db_data    (or: make docker-down-clean)
```

### Individual service builds

```bash
# Backend only
docker build -t bob-intelligence-backend ./backend

# Frontend only
docker build -t bob-intelligence-frontend ./frontend
```

### Environment variables in Docker

Backend env vars are loaded from `backend/.env` via the `env_file` directive in `docker-compose.yml`.

The frontend uses relative `/api/*` paths — `VITE_API_BASE_URL` is intentionally left empty in `frontend/.env.docker` and nginx proxies API calls to the backend at runtime. You only need to set `VITE_API_BASE_URL` when deploying the frontend and backend on different origins (e.g. a separate CDN).

At runtime, the nginx container reads `BACKEND_HOST` (default `backend:8000`) and substitutes it into `nginx.conf` via `envsubst`. Override it in `docker-compose.yml` if you're deploying the backend separately:

```yaml
environment:
  BACKEND_HOST: my-backend-service:8000
```

### Production deployment notes

- The SQLite database is persisted automatically. `docker-compose.yml` declares a named volume `db_data` mounted at `/app` on the backend container — no manual configuration required. To wipe the database: `docker compose down -v`.
- For production scale, set `DATABASE_URL` to a PostgreSQL connection string — SQLAlchemy will use it without any code changes.
- The backend Dockerfile installs the IBM Bob CLI via the official install script. If `LLM_PROVIDER` is not `bob`, you can remove those steps to reduce image size.

---

## API Reference

Full interactive documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/stories` | List all imported stories |
| `POST` | `/api/stories/import` | Import from Jira (`import_source=jira`) or sample data (`import_source=sample`) |
| `GET` | `/api/stories/{id}` | Get a single story |
| `POST` | `/api/recommendations` | Generate a priority + execution-mode recommendation |
| `GET` | `/api/recommendations/{id}` | Retrieve a saved recommendation |
| `PATCH` | `/api/recommendations/{id}/mode-approve` | Tech-lead approval of execution mode |
| `PATCH` | `/api/recommendations/{id}/mode-override` | Tech-lead override (requires `override_reason`) |
| `POST` | `/api/resolved-tickets/import` | Import resolved tickets from Jira or sample data (sample tickets are auto-seeded on startup) |
| `GET` | `/api/resolved-tickets` | List all resolved tickets |
| `POST` | `/api/bob-sessions` | Record a Bob execution session (gated: requires approved recommendation) |
| `POST` | `/api/outcomes` | Record an outcome (gated: requires approved recommendation) |

---

## Testing

### Unit & Integration Tests (pytest)

Tests use an isolated in-memory SQLite database (`bob_intelligence_test.db`) and stub out all LLM calls. The production database is never touched.

```bash
# From the repo root, with the virtual environment active:

# Run the full test suite
pytest

# Run a specific milestone test file
pytest backend/tests/test_milestone2.py -v
pytest backend/tests/test_milestone3.py -v
pytest backend/tests/test_milestone4a.py -v
pytest backend/tests/test_milestone4b.py -v

# Run with coverage (requires pytest-cov — install once)
pip install pytest-cov
pytest --cov=backend --cov-report=term-missing  # or: make test-cov

# Run only tests matching a keyword
pytest -k "priority" -v

# Stop on first failure
pytest -x
```

**Test files:**

| File | Coverage |
|---|---|
| `test_milestone2.py` | DB init, story import, Jira service, duplicate handling |
| `test_milestone3.py` | Recommendation engine, priority ranking, execution mode, approval/override gates |
| `test_milestone4a.py` | Resolved-ticket import, semantic similarity, `evidence_confidence`, `similar_tickets` |
| `test_milestone4b.py` | PR evidence discovery, LLM analysis stubs, `supporting_prs`, `code_analysis_notes` |
| `test_priority_eligibility.py` | Priority scoring edge cases |
| `test_ac_quality.py` | Acceptance-criteria quality signals |
| `test_ac_adversarial.py` | Adversarial AC inputs |
| `test_correctness_m4b_prereq.py` | M4b prerequisite correctness checks |
| `test_hardening.py` | Hardening / regression tests |

### Smoke Test (end-to-end shell)

The smoke test runs a full flow against a **live running backend** using `curl` and `python3`. It does not require Jira credentials.

```bash
# Start the backend first (either locally or via Docker)
uvicorn backend.main:app --port 8000
# or: docker compose up

# In a separate terminal:
bash scripts/smoke_test.sh

# Point at a non-default backend URL:
BASE_URL=http://localhost:8000 bash scripts/smoke_test.sh
```

The script exercises:
1. Health check
2. Sample story import (idempotency check)
3. Sample resolved-ticket import (idempotency check)
4. `GET /api/resolved-tickets`
5. Jira import with no credentials (asserts `credentials_missing`)
6. `POST /api/recommendations` — asserts mode, priority rank, evidence fields, `similar_tickets`, `evidence_confidence`, `supporting_prs`
7. Override validation (missing/empty `override_reason` → 422)
8. Bob-session gate (409 while `mode_approval_status=pending`)
9. Outcomes gate (409 while `mode_approval_status=pending`)
10. Tech-lead approval (`PATCH .../mode-approve`)
11. Bob-session gate passes after approval (501 not 409)
12. Outcomes gate passes after approval (501 not 409)
13. Recommendation persistence with M4a fields

---

## LLM Provider Configuration

Set `LLM_PROVIDER` in `backend/.env`:

| Provider | `LLM_PROVIDER` value | Additional required vars |
|---|---|---|
| IBM Bob CLI (default) | `bob` | `LLM_API_KEY` (= `BOB_API_KEY`) |
| OpenAI | `openai` | `LLM_API_KEY`; optionally `LLM_MODEL` (default `gpt-4o-mini`) and `LLM_ENDPOINT` |
| IBM watsonx.ai | `watsonx` | `LLM_API_KEY`, `LLM_ENDPOINT`, `LLM_PROJECT_ID`; optionally `LLM_MODEL` |

When `LLM_API_KEY` is absent, the execution-mode recommendation falls back to the deterministic rule engine (`mode=collaborative`) and the `uncertainty_note` field in the response is explicitly flagged as not evidence-based.

---

## Jira Integration

Set the three Jira variables in `backend/.env`:

```dotenv
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_USER_EMAIL=you@example.com
JIRA_API_TOKEN=<token from id.atlassian.com>
```

Then import a story via the UI or API:

```bash
curl -X POST http://localhost:8000/api/stories/import \
  -H "Content-Type: application/json" \
  -d '{"import_source": "jira", "jira_key": "PIE-42"}'
```

If credentials are absent or the Jira call fails, the response includes `source_status: "credentials_missing"` or `"jira_error"` and an explicit `source_warning`. Sample data is **never** silently substituted.

---

## GitHub PR Enrichment

Set `GITHUB_TOKEN` in `backend/.env` (optional for public repos, required for private):

```dotenv
GITHUB_TOKEN=ghp_...
```

When a recommendation is generated, `historical_evidence_service` fetches PR metadata for similar resolved tickets and populates `supporting_prs` and `code_analysis_notes` in the recommendation response. If the token is absent on a private repo, PR enrichment is skipped and a `source_warning` is recorded in the recommendation.
