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

## Entry 2

**Date:** 2025-07-15
**Objective:** Milestone 2 — Data layer and story import

**Prompt summary:** Implement Milestone 2 from the plan: SQLAlchemy 2.x file-backed SQLite, all 6 ORM models, `POST /api/stories/import`, `GET /api/stories`, `GET /api/stories/{id}`, `GET /api/developer-profiles`, `POST /api/developer-profiles/import-sample`, Jira REST v3 service, sample data, pytest test suite. Identify and resolve any plan contradictions before implementing.

### Schema contradiction identified and resolved

The plan specified a single `approval_status` field on `Recommendation`, but the product requires independent approval/override tracking for two separate decisions (execution mode and developer match). A single field cannot represent these independently.

**Resolution (minimal schema addition):** replaced `approval_status` with two independent sets of fields:
- `mode_approval_status` / `mode_approved_by` / `mode_approved_at` / `mode_override_reason`
- `dev_match_approval_status` / `dev_match_approved_by` / `dev_match_approved_at` / `dev_match_override_reason`

Ticket prioritization is advisory only — no approval gate needed.

### Files created / modified

| File | Change |
|------|--------|
| `backend/database.py` | Updated: file-backed SQLite (`bob_intelligence.db`), added `init_db()`, lifespan startup wiring |
| `backend/models.py` | Created: all 6 ORM models with split approval status schema |
| `backend/schemas.py` | Created: Pydantic schemas for story import/list, developer profile list |
| `backend/main.py` | Updated: registered stories + developer-profiles routers, replaced `on_event` with lifespan |
| `backend/routers/stories.py` | Created: `GET /api/stories`, `POST /api/stories/import`, `GET /api/stories/{id}` |
| `backend/routers/developer_profiles.py` | Created: `GET /api/developer-profiles`, `POST .../import-sample` |
| `backend/services/jira_service.py` | Created: Jira REST v3 fetch, custom field validation, sample data loader |
| `backend/sample_data/stories.json` | Created: 3 PIE-domain sample stories, clearly labeled `[SAMPLE DATA]` |
| `backend/sample_data/developer_profiles.json` | Created: 3 sample developer profiles, clearly labeled `[SAMPLE DATA]` |
| `backend/conftest.py` | Created: test fixtures with DB isolation (`bob_intelligence_test.db`) |
| `backend/tests/__init__.py` | Created |
| `backend/tests/test_milestone2.py` | Created: 33 pytest tests |
| `backend/pytest.ini` | Updated: added `testpaths` |
| `.bob/context.md` | Updated: reflects Milestone 2 complete state |

### Implemented vs proposed

| Item | Status |
|------|--------|
| File-backed SQLite at `bob_intelligence.db` | ✅ Implemented |
| All 6 ORM models | ✅ Implemented |
| Split approval status schema (contradiction resolved) | ✅ Implemented |
| `POST /api/stories/import` (Jira + sample) | ✅ Implemented |
| `GET /api/stories` | ✅ Implemented |
| `GET /api/stories/{id}` | ✅ Implemented |
| `GET /api/developer-profiles` | ✅ Implemented |
| `POST /api/developer-profiles/import-sample` | ✅ Implemented |
| Jira service — credentials_missing / jira_error paths | ✅ Implemented |
| Jira service — custom field validation with source_warning | ✅ Implemented |
| No silent sample data substitution | ✅ Implemented and tested |
| Duplicate import prevention | ✅ Implemented (idempotent by jira_key / jira_account_id) |
| story_points as metadata only | ✅ Implemented and tested |
| Test isolation (bob_intelligence_test.db, never production) | ✅ Implemented |
| 33 pytest tests | ✅ All passing |
| `linked_prs` populated from Jira dev-status API | ⏳ Deferred to Milestone 4 |
| Developer profile bootstrap from Jira | ⏳ Not in plan scope yet |
| Recommendation engine | ⏳ Milestone 3 |

### Verification performed

- `python3 -m pytest backend/tests/test_milestone2.py -v` → **33 passed, 0 failed** (verified 2025-07-15)
- `bash scripts/smoke_test.sh` → **PASSED** — health check still exits 0 after Milestone 2 changes
- Backend starts cleanly: `uvicorn backend.main:app --port 8000` — `bob_intelligence.db` created on startup, tables created, no errors
- `POST /api/stories/import` with `import_source="sample"` returns `source_status="sample_import"` with all 3 PIE stories labeled `source="sample"` — verified manually
- `POST /api/stories/import` with `import_source="jira"` and no credentials returns `source_status="credentials_missing"`, empty stories array — no silent substitution — verified by test and manually
- Second sample import returns `skipped_duplicates=3`, `stories=[]` — idempotency verified

### Known limitations

- `linked_prs` is always `[]` on Jira import — the dev-status API call is a separate HTTP request deferred to Milestone 4.
- Jira custom field keys (`JIRA_STORY_POINTS_FIELD`, `JIRA_AC_FIELD`) have not been validated against a real Jira instance — service will return `source_warning` when fields are missing.
- Developer profile `verified_skills`, `verified_pr_count`, `verified_review_count`, `recent_domains` are empty at cold start. Planned bootstrap path: Jira dev-status API to get merged PR links from resolved tickets, extract author/reviewer/file-path data, present to tech lead for confirmation before writing to profile.
- Tests must be run from project root (`python3 -m pytest backend/tests/test_milestone2.py -v`), not from `backend/` directory, due to `backend.*` import paths.

### Value delivered

- All tables exist and persist across backend restarts — verified by persistence test.
- Story import is fully wired: live Jira when credentials are set, explicit sample import when not, with clear `source_status` on every code path.
- No silent data substitution anywhere in the import path — every failure returns a clear `source_warning`.
- 33 automated tests cover all Milestone 2 acceptance criteria and prevent regressions in future milestones.
- Schema contradiction (single approval_status) resolved before any downstream code was written — Milestone 3 can implement independent approval gates without a migration.

---
