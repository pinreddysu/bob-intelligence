# BOB_USAGE.md — Bob Intelligence Activity Log

Chronological record of meaningful Bob development tasks.
Updated after tasks are completed and results are verified.
Dates, files, and results reflect actual work — nothing is invented.

---

## Entry 1

**Date:** 2025-07-14
**Objective:** Milestone 1 — Scaffold and documentation baseline
**Prompt summary:** Implement Milestone 1 from the plan: create directory structure, FastAPI backend with `GET /api/health`, `requirements.txt`, frontend `package.json`, `.env.example`, smoke test script, and initial documentation files. Check installed versions first.

### Files created

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app entry point; `GET /api/health` endpoint |
| `backend/database.py` | SQLAlchemy engine + session factory (in-memory SQLite) |
| `backend/models.py` | ORM models placeholder |
| `backend/schemas.py` | Pydantic schemas placeholder |
| `backend/routers/__init__.py` | Router package |
| `backend/routers/stories.py` | Stories router placeholder |
| `backend/routers/recommendations.py` | Recommendations router placeholder |
| `backend/routers/bob_sessions.py` | Bob sessions router placeholder |
| `backend/routers/outcomes.py` | Outcomes router placeholder |
| `backend/services/__init__.py` | Services package |
| `backend/services/jira_service.py` | Jira service placeholder |
| `backend/services/recommendation_service.py` | Recommendation service placeholder |
| `backend/services/evidence_service.py` | Evidence service placeholder |
| `backend/requirements.txt` | Production dependencies (pinned) |
| `backend/requirements-dev.txt` | Test/dev dependencies |
| `backend/.env.example` | Environment variable template |
| `frontend/package.json` | Node dependencies (React 19, Vite 6, react-router-dom 7) |
| `frontend/tsconfig.json` | TypeScript compiler config |
| `frontend/vite.config.ts` | Vite config with /api proxy |
| `frontend/index.html` | HTML entry point |
| `frontend/src/main.tsx` | React router and app entry |
| `frontend/src/pages/StorySelector.tsx` | Step 1 placeholder |
| `frontend/src/pages/RecommendationView.tsx` | Step 2 placeholder |
| `frontend/src/pages/LinkBobWork.tsx` | Step 3 placeholder |
| `frontend/src/pages/OutcomeComparison.tsx` | Step 4 placeholder |
| `frontend/src/api/client.ts` | API client stub + healthCheck() |
| `scripts/smoke_test.sh` | Milestone 1 smoke test (health check only) |
| `.gitignore` | Python + Node + env exclusions |
| `context.md` | Product context and implementation status |
| `rules.md` | Persistent Bob operating rules |
| `BOB_USAGE.md` | This file |

### Implemented vs proposed

| Item | Status |
|------|--------|
| Directory structure per plan | ✅ Implemented |
| `GET /api/health` → `{"status":"ok"}` | ✅ Implemented and verified |
| `requirements.txt` with pinned deps | ✅ Implemented |
| Frontend `package.json` with correct deps | ✅ Implemented |
| `.env.example` with all env vars | ✅ Implemented |
| `scripts/smoke_test.sh` (health only) | ✅ Implemented |
| `context.md`, `rules.md`, `BOB_USAGE.md` | ✅ Implemented |
| Router and service placeholders | ✅ Created (stubs only, no logic) |
| Frontend page stubs | ✅ Created (placeholder UI, no backend calls) |

### Verification performed

- Python 3.14.7, pip 26.2.1, Node v26.9.0, npm 11.19.1 confirmed via CLI before choosing dependency versions.
- All dependency versions confirmed available via `pip3 index versions` before pinning.
- **pydantic 2.11.7 → upgraded to 2.14.0**: `pydantic-core 2.33.2` (paired with 2.11.7) uses PyO3 0.24.1 which declares Python 3.13 as its maximum. `pydantic 2.14.0` pairs with `pydantic-core 2.50.0` which ships a pre-built `cp314-macosx_11_0_arm64.whl` — no source build needed.
- `pip3 install -r backend/requirements.txt` → **SUCCESS** — all 22 packages installed cleanly.
- `uvicorn main:app --port 8000` started; `curl http://localhost:8000/api/health` → `{"status":"ok"}` (HTTP 200). **VERIFIED**.
- `bash scripts/smoke_test.sh` → **PASSED** (exit 0). Output: `✓ Health check passed`.
- `python3 -m pytest --collect-only` (dev deps installed) → 0 tests collected, no warnings (exit 5 = expected for Milestone 1).

### Known limitations

- All router and service files are stubs — no business logic yet.
- Frontend pages are placeholder shells with no backend calls.
- In-memory SQLite: data does not persist across backend restarts.
- Jira field keys (story points, acceptance criteria) unresolved — requires Milestone 2 validation.
- Git evidence capture unverified — requires Milestone 4.
- Bob session association is manual (no automatic hook) — confirmed design, not a bug.

### Value delivered

- Repository is fully scaffolded and runnable from scratch.
- All import paths, module names, and directory structure are established for Milestones 2–7.
- `GET /api/health` provides an immediate integration smoke test for CI and local dev.
- `.env.example` documents all required credentials without exposing secrets.
- Demo can be cloned and the backend started in under 2 minutes.

---

*Future entries will be appended below after each meaningful milestone.*
