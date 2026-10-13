# Bob Intelligence — Context

## Product Goal

Bob Intelligence helps teams decide how to execute a Jira story with IBM Bob before implementation begins, then learn from the verified outcome.

For a selected story the product:
1. Understands the story description, acceptance criteria, repository context, and risks.
2. Recommends one of three execution modes: Bob-led, Collaborative, or Human-led.
3. Explains the recommendation using evidence, risks, counterevidence, and uncertainty.
4. Links the recommendation to actual Bob-assisted work.
5. Records verifiable outcomes (changed files, test results, build results, AC met).
6. Compares the original recommendation with the actual outcome.
7. Preserves completed-task evidence to inform future recommendations.

## Technology Stack

| Layer | Choice | Version |
|-------|--------|---------|
| Backend | Python + FastAPI | Python 3.14.7, FastAPI 0.115.14 |
| ASGI server | Uvicorn | 0.34.3 |
| ORM | SQLAlchemy | 2.0.41 |
| Validation | Pydantic | 2.14.0 (pydantic-core 2.50.0, cp314 wheel) |
| HTTP client | httpx | 0.28.1 |
| Database | File-backed SQLite (`bob_intelligence.db`) | (via SQLAlchemy) |
| Frontend | React + TypeScript | React 19, TS 5.8 |
| Bundler | Vite | 6.x |
| Router | react-router-dom | 7.x |
| Node | v26.9.0 | npm 11.19.1 |

## Architecture Summary

```
Browser (React/Vite :5173)
     │  REST JSON  (proxied via Vite → :8000 in dev)
     ▼
FastAPI (backend/main.py :8000)
     ├── /api/stories              → jira_service  (Jira REST v3 or explicit sample import)
     ├── /api/developer-profiles   → sample import only (preserved; not used for recommendations in MVP)
     ├── /api/recommendations      → recommendation_service (priority + mode — Milestone 3)
     ├── /api/bob-sessions         → SQLite (manual explicit link — Milestone 4)
     └── /api/outcomes             → evidence_service + SQLite (Milestone 5)
```

No automatic Bob session telemetry. Bob sessions are created by explicit POST.

## Repository Structure

```
bob-intelligence/
├── backend/
│   ├── main.py               FastAPI app + /api/health + lifespan DB init
│   ├── database.py           SQLAlchemy engine + session + init_db()
│   ├── models.py             ORM models (all 6 entities — Milestone 2)
│   ├── schemas.py            Pydantic schemas (Story, DeveloperProfile — Milestone 2)
│   ├── routers/
│   │   ├── stories.py        GET /api/stories, POST /api/stories/import, GET /api/stories/{id}
│   │   ├── developer_profiles.py  GET /api/developer-profiles, POST .../import-sample
│   │   ├── recommendations.py     POST /api/recommendations, GET /{id}, PATCH .../mode-approve, PATCH .../mode-override
│   │   ├── bob_sessions.py        409 gate active; full impl Milestone 4
│   │   └── outcomes.py            409 gate active; full impl Milestone 5
│   ├── services/
│   │   ├── jira_service.py   Jira REST v3 fetch + sample data loader
│   │   ├── recommendation_service.py  Priority engine + mode engine (Milestone 3)
│   │   └── evidence_service.py        placeholder (Milestone 4)
│   ├── sample_data/
│   │   ├── stories.json            3 PIE-domain sample stories [SAMPLE DATA]
│   │   └── developer_profiles.json 3 sample developer profiles [SAMPLE DATA]
│   ├── tests/
│   │   ├── test_milestone2.py      33 pytest tests (all passing)
│   │   └── test_milestone3.py      42 pytest tests (all passing)
│   ├── conftest.py           Test fixtures + DB isolation
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/            4 wizard-step pages (placeholder shells)
│   │   ├── api/              Typed fetch wrappers
│   │   └── main.tsx          Router
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── scripts/
│   └── smoke_test.sh         Milestone 1 health check (passes)
├── .bob/context.md
├── BOB_USAGE.md
└── bob-intelligence-plan.md
```

## Implementation Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| 1 — Scaffold + docs baseline | ✅ Complete | Health endpoint verified. Smoke test exits 0. |
| 2 — Data layer + story import | ✅ Complete | 33/33 tests passing. |
| 3 — Recommendation engine | ✅ Complete | 75/75 tests passing. Smoke test 20/20. |
| 4 — Bob session link + evidence | ⬜ Pending | 409 gate active; full impl pending |
| 5 — Outcome + comparison | ⬜ Pending | 409 gate active; full impl pending |
| 6 — React frontend | ⬜ Pending | Placeholder pages exist |
| 7 — Smoke test + demo readiness | ⬜ Pending | |

## Milestone 2 — What Was Implemented

### Database
- `database.py` updated: file-backed SQLite at `bob_intelligence.db` (was in-memory). `init_db()` added — called via FastAPI lifespan on startup. Safe to call on every restart (no-op if tables exist).
- Tests use isolated `bob_intelligence_test.db`, created fresh each session and deleted on teardown. Production DB is never touched by tests.

### ORM Models (all 6 entities)
- `Story` — jira_key, title, description, acceptance_criteria, story_points (metadata only), labels, priority, status, assignee, blockers, linked_prs, source, created_at
- `DeveloperProfile` — display_name, jira_account_id, verified_skills, verified_pr_count, verified_review_count, recent_domains, availability_note, source
- `Recommendation` — all three decision fields (priority, mode, dev-match) with independent approval gates per decision (see schema note below)
- `BobSession` — summary, files_changed, pie_commit_sha
- `Outcome` — test_result, build_result, ac_met, diff_summary, developer_id FK
- `Comparison` — mode_verdict, dev_match_verdict

### Schema Adjustment — Approval Status
The plan specified a single `approval_status` field on `Recommendation`, but the product requires independent approval for execution-mode and developer-match decisions. A single field cannot represent these independently.

**Resolution (minimal):** replaced `approval_status` with two independent sets:
- `mode_approval_status` / `mode_approved_by` / `mode_approved_at` / `mode_override_reason`
- `dev_match_approval_status` / `dev_match_approved_by` / `dev_match_approved_at` / `dev_match_override_reason`

Ticket prioritization is advisory — no approval gate needed.

### Endpoints Implemented
| Method | Path | Status |
|--------|------|--------|
| GET | /api/health | ✅ Milestone 1 |
| GET | /api/stories | ✅ Milestone 2 |
| POST | /api/stories/import | ✅ Milestone 2 |
| GET | /api/stories/{id} | ✅ Milestone 2 |
| GET | /api/developer-profiles | ✅ Milestone 2 |
| POST | /api/developer-profiles/import-sample | ✅ Milestone 2 |
| POST | /api/recommendations | ✅ Milestone 3 |
| GET | /api/recommendations/{id} | ✅ Milestone 3 |
| PATCH | /api/recommendations/{id}/mode-approve | ✅ Milestone 3 |
| PATCH | /api/recommendations/{id}/mode-override | ✅ Milestone 3 |
| POST | /api/bob-sessions | ⚠️ Gate active (409 on pending), full impl Milestone 4 |
| POST | /api/outcomes | ⚠️ Gate active (409 on pending), full impl Milestone 5 |

### Jira Service
- `fetch_from_jira(jira_key)` — calls Jira REST API v3, validates custom field keys for story points and AC, returns `source_status` and `source_warning` on every code path
- `load_sample_stories()` / `load_sample_developer_profiles()` — loads from JSON files, enforces `source="sample"`
- Never silently substitutes sample data for a failed Jira import
- `source_status` values: `"jira"` | `"sample_import"` | `"credentials_missing"` | `"jira_error"`

### Sample Data
- `backend/sample_data/stories.json` — 3 PIE-domain stories (PIE-42, PIE-38, PIE-45), clearly labeled `[SAMPLE DATA]`
- `backend/sample_data/developer_profiles.json` — 3 developer profiles (Alex Chen, Priya Nair, Jordan Kim), clearly labeled

### Tests
- 33 pytest tests in `backend/tests/test_milestone2.py` — all passing
- Run from project root: `python3 -m pytest backend/tests/test_milestone2.py -v`

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Navigation | Wizard-style (4 screens — dev-match removed) | Demo clarity; developer match deferred |
| Sample story | PIE-domain ("Add portfolio rebalancing endpoint") | Realistic domain context |
| Jira fallback | Explicit `source_status` + `source_warning` on failure; no silent substitution | Demo transparency |
| Recommendation logic | Pure rule engine — priority + execution mode only | Developer match deferred to future phase |
| Bob session capture | Explicit POST (no telemetry assumed) | Confirmed: Bob has no session-history API |
| DB | File-backed SQLite (`bob_intelligence.db`) | Records persist across restarts; tests use isolated `bob_intelligence_test.db` |
| Story points | Imported metadata only — not used for recommendations | Out of scope per MVP rules |
| Approval status | `mode_approval_status` only in MVP; `dev_match_approval_status` in model but unused | Developer match deferred |
| Developer match | **DEFERRED** — model + sample data preserved; no ranking, skill verification, team matching, or GitHub integration | Deferred to Milestone 8 (future phase) |

## How to Configure Jira

Set the following in `backend/.env` (copy from `.env.example`):

```bash
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_USER_EMAIL=you@example.com
JIRA_API_TOKEN=your_token   # https://id.atlassian.com/manage-profile/security/api-tokens

# Validate these by calling:
#   GET /rest/api/3/issue/{key}?expand=names
# on a known story and inspecting the returned field names.
JIRA_STORY_POINTS_FIELD=customfield_10016   # verify — varies by instance
JIRA_AC_FIELD=                              # verify — varies by instance; leave blank if unknown
```

If any credential is missing, `POST /api/stories/import` with `import_source="jira"` returns
`source_status="credentials_missing"` and a non-empty `source_warning`. No sample data is
substituted silently.

## How to Import Sample Data

Sample data import is an explicit action — it is never triggered automatically.

```bash
# Import sample stories (idempotent — duplicates skipped)
curl -X POST http://localhost:8000/api/stories/import \
  -H "Content-Type: application/json" \
  -d '{"import_source": "sample"}'

# Import sample developer profiles (idempotent — duplicates skipped)
curl -X POST http://localhost:8000/api/developer-profiles/import-sample
```

Both endpoints skip records already in the DB (matched by `jira_key` / `jira_account_id`)
and return `skipped_duplicates` in the response.

## How to Run the Backend

```bash
# From project root
pip3 install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000

# Health check
curl http://localhost:8000/api/health   # → {"status":"ok"}
```

`bob_intelligence.db` is created automatically in the project root on first startup.

## How to Run Tests

```bash
# Always run from project root, not from backend/
pip3 install -r backend/requirements-dev.txt
python3 -m pytest backend/tests/test_milestone2.py -v
# Expected: 33 passed
```

Tests use `bob_intelligence_test.db` (created and deleted automatically).
Production `bob_intelligence.db` is never touched by tests.

## Milestone 3 — What Was Implemented

### Recommendation Engine (`backend/services/recommendation_service.py`)

Two independent sub-engines, both deterministic and explainable:

**Priority engine** — scores each story on:
- Jira `priority` field (highest=+30, high=+30, medium=+15, low/lowest=+5)
- Urgency/risk labels (`security`, `p0`, `incident`, etc.) → +25
- Status readiness (`Ready for Dev` → +20, `In Progress` → +10)
- Acceptance criteria completeness → +10
- Blockers → -20 per blocker
- Open unknowns in description text (regex-matched) → -10 when ≥3
- Returns `priority_rank` (1 = highest) relative to all stories in DB

**Mode engine** — scores story toward `bob_led` (>10), `human_led` (<-10), or `collaborative`:
- Acceptance criteria length → +10 when detailed, -10 when absent
- Open unknowns in description → -15 (≥3) or -5 (1–2)
- Description length → +5 (>300 chars) or -10 (<50 chars)
- Blockers → -15
- Linked PRs → +5
- Historical outcomes: when 0 exist, `uncertainty_note` states "no historical outcomes available"

> **Label signals removed:** `_BOB_LED_LABELS`, `_HUMAN_LED_LABELS`, `_COLLAB_LABELS` were removed. Label taxonomies are org-specific — a `"security"` label at one company means something different at another. Mode is now driven entirely by story-structure signals and (in M4a+) historical evidence.

**Design constraints enforced:**
- `story_points` is never read by either engine
- All evidence items carry `source`, `description`, and `verified: bool`
- Each recommendation includes `mode_risks[]`, `mode_counterevidence[]`, and `uncertainty_note`
- `mode_approval_status` is always `"pending"` on creation
- Calling `POST /api/recommendations` twice for the same story supersedes the first (status → `"superseded"`)
- Developer-match fields (`suggested_developer`, `dev_match_*`, etc.) remain null/empty — deferred

### Approval / Override Endpoints

- `PATCH .../mode-approve`: sets `mode_approval_status="approved"`, records `mode_approved_by` + `mode_approved_at`
- `PATCH .../mode-override`: sets `mode_approval_status="overridden"`, records all three fields; returns 422 when `override_reason` is missing or empty; optionally updates `mode`

### Downstream 409 Gates

Both `POST /api/bob-sessions` and `POST /api/outcomes` return **409 Conflict** when the story's latest recommendation has `mode_approval_status="pending"`. The gate is not triggered when no recommendation exists at all (recommendation step not yet run). Full session/outcome implementation deferred to Milestones 4 and 5.

### Clarification: Advisory Priority vs. Ticket Selection

Priority rank is **advisory** — it surfaces the highest-priority story for the tech lead to review. The tech lead **explicitly selects** a story from the ranked list (a human choice, no gate, no approval). Only after selection does the system generate an execution-mode recommendation, and only that mode recommendation requires approval. There is no `priority_approval_status` field and no separate priority approval endpoint.

## Known Limitations

- **Developer match deferred.** `DeveloperProfile` model, sample data, `GET /api/developer-profiles`, and `POST /api/developer-profiles/import-sample` are preserved but not used for recommendations in the current MVP. Developer ranking, skill verification, team matching, and GitHub/Jira bootstrap are out of scope until Milestone 8.
- **Jira custom field keys unverified on real instance.** `JIRA_STORY_POINTS_FIELD` and `JIRA_AC_FIELD` vary by instance. The service validates their presence and returns a `source_warning` if missing, but correct values must be confirmed against a real Jira instance via `GET /rest/api/3/issue/{key}?expand=names`.
- **`linked_prs` always empty on Jira import.** The dev-status API call needed to populate PR links requires a separate HTTP call; deferred to Milestone 4.
- **Bob session and outcome endpoints return 501** after the approval gate passes — full implementation is in Milestones 4 and 5 respectively.
- **Bob session association is manual.** No automatic hook — confirmed design, not a bug.
- **Frontend pages are placeholder shells.** Real UI in Milestone 6.
- **Git evidence capture unverified.** Requires Milestone 4 and a real PIE repo path.

## Next Steps

1. **Milestone 4a** — Historical ticket retrieval and semantic similarity (TF-IDF cosine, `historical_evidence_service`, `ResolvedTicket` model, `POST /api/resolved-tickets/import`, `GET /api/resolved-tickets`, mode score enrichment).
2. **Milestone 4b** — PR evidence discovery and current-code analysis.
3. **Milestone 4c** — Bob session link (full implementation).
4. **Milestone 5** — Outcome recording and mode comparison.
5. **Milestone 6** — React frontend (4-screen wizard, no Developer Match screen).
6. **Milestone 7** — Smoke test and demo readiness.
7. **Milestone 8 (future)** — Developer match: Jira/GitHub bootstrap, skill verification, team matching, dev-match approval gate.
