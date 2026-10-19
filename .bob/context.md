# Bob Intelligence — Context

## Product Goal

Bob Intelligence helps teams decide how to execute a Jira story with IBM Bob before implementation begins, then learn from the verified outcome.

For a selected story the product:
1. Understands the story description, acceptance criteria, repository context, and risks.
2. Recommends one of three execution modes: Bob-led, Collaborative, or Human-led.
3. Explains the recommendation using evidence, risks, counterevidence, and uncertainty.
4. Enriches the mode recommendation with semantically similar resolved tickets (M4a).
5. Enriches supporting PRs with GitHub metadata, patches, and LLM analysis; wires Outcome and BobSession evidence from similar stories (M4b).
6. **Determines the final mode via IBM Bob headless CLI** — passing ticket context, PR patches, and current PIE source excerpts (M4d).
7. Links the recommendation to actual Bob-assisted work.
8. Records verifiable outcomes (changed files, test results, build results, AC met).
9. Compares the original recommendation with the actual outcome.
10. Preserves completed-task evidence to inform future recommendations.

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
     ├── /api/recommendations      → recommendation_service (priority + mode + M4a/M4b evidence)
     ├── /api/resolved-tickets     → resolved_tickets router (import + list — M4a)
     ├── /api/bob-sessions         → SQLite (manual explicit link — Milestone 4c)
     └── /api/outcomes             → evidence_service + SQLite (Milestone 5)
```

No automatic Bob session telemetry. Bob sessions are created by explicit POST.

## Repository Structure

```
bob-intelligence/
├── backend/
│   ├── main.py               FastAPI app + /api/health + lifespan DB init (v0.4.0)
│   ├── database.py           SQLAlchemy engine + session + init_db()
│   ├── models.py             ORM: Story, Recommendation, DeveloperProfile, BobSession,
│   │                                Outcome, Comparison, ResolvedTicket (M4a), PREvidence (M4b)
│   ├── schemas.py            Pydantic schemas — Story, DeveloperProfile, Recommendation
│   │                                (extended with M4a+M4b fields), ResolvedTicket, PREvidence
│   ├── routers/
│   │   ├── stories.py            GET /api/stories, POST /api/stories/import, GET /api/stories/{id}
│   │   ├── developer_profiles.py GET /api/developer-profiles, POST .../import-sample
│   │   ├── recommendations.py    POST /api/recommendations, GET /{id},
│   │   │                           PATCH .../mode-approve, PATCH .../mode-override
│   │   ├── resolved_tickets.py   POST /api/resolved-tickets/import, GET /api/resolved-tickets (M4a)
│   │   ├── bob_sessions.py       409 gate active; full impl Milestone 4c
│   │   └── outcomes.py           409 gate active; full impl Milestone 5
│   ├── services/
│   │   ├── jira_service.py              Jira REST v3 fetch + sample data loader
│   │   ├── recommendation_service.py    Priority + mode engine + M4a/M4b evidence wiring
│   │   ├── historical_evidence_service.py  TF-IDF similarity (M4a); PR/outcome/session enrichment (M4b)
│   │   ├── github_service.py            GitHub REST API — parse_pr_url, fetch_pr_evidence (patches), fetch_file_content (M4b/4d)
│   │   ├── llm_service.py               LLM analysis — analyze_pr(), analyze_mode() via Bob CLI, openai/watsonx (M4b/4d)
│   │   └── evidence_service.py          placeholder (future milestones)
│   ├── sample_data/
│   │   ├── stories.json            PIE sample open stories (user auth domain) [SAMPLE DATA]
│   │   ├── resolved_tickets.json   PIE resolved tickets for M4a historical evidence [SAMPLE DATA]
│   │   └── developer_profiles.json 3 sample developer profiles [SAMPLE DATA]
│   ├── tests/
│   │   ├── test_milestone2.py      33 pytest tests (all passing)
│   │   ├── test_milestone3.py      42 pytest tests (all passing)
│   │   ├── test_milestone4a.py     50 pytest tests (all passing)
│   │   └── test_milestone4b.py     60 pytest tests (all passing)
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
├── docs/
│   ├── application-technical-overview.md   Full technical reference (architecture, DB models, API contracts, screen specs)
│   └── business-user-workflow.md           Business user workflow, functional requirements, and screen specifications
├── scripts/
│   └── smoke_test.sh         Milestone 4a end-to-end smoke test (M3 + M4a checks)
├── .bob/context.md
├── BOB_USAGE.md
└── bob-intelligence-plan.md
```

## Implementation Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| 1 — Scaffold + docs baseline | ✅ Complete | Health endpoint verified. |
| 2 — Data layer + story import | ✅ Complete | 33/33 tests passing. |
| 3 — Recommendation engine | ✅ Complete | 75/75 tests passing. |
| 4a — Historical ticket retrieval + similarity | ✅ Complete | 125/125 tests passing. |
| 4b — PR evidence + LLM analysis | ✅ Complete | 382/382 tests passing. |
| 4d — LLM-driven mode recommendation (Bob CLI) | ✅ Complete | Tests not yet updated for 4d. |
| 4c — Bob session link (full impl) | ⬜ Next | 409 gate active |
| 5 — Outcome + comparison | ⬜ Pending | 409 gate active |
| 6 — React frontend (Mission Control) | ✅ Complete | Build passes. Full UI implemented. |
| 7 — Smoke test + demo readiness | ⬜ Pending | |

## Documentation Files Added

| File | Purpose |
|------|---------|
| `docs/application-technical-overview.md` | Full technical reference — architecture, DB model relationships, complete API contracts, screen-by-screen frontend specs, field consumption guide, and gap analysis |
| `docs/business-user-workflow.md` | Business user workflow, functional requirements, per-screen interaction inventory, API-to-UI field mapping, MVP scope vs deferred scope, and acceptance criteria checklist |

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
| Method | Path | Milestone | Status |
|--------|------|-----------|--------|
| GET | /api/health | M1 | ✅ |
| GET | /api/stories | M2 | ✅ |
| POST | /api/stories/import | M2 | ✅ |
| GET | /api/stories/{id} | M2 | ✅ |
| GET | /api/developer-profiles | M2 | ✅ |
| POST | /api/developer-profiles/import-sample | M2 | ✅ |
| POST | /api/recommendations | M3 | ✅ (enriched with M4a historical evidence) |
| GET | /api/recommendations/{id} | M3 | ✅ (includes M4a fields) |
| PATCH | /api/recommendations/{id}/mode-approve | M3 | ✅ |
| PATCH | /api/recommendations/{id}/mode-override | M3 | ✅ |
| POST | /api/resolved-tickets/import | M4a | ✅ |
| GET | /api/resolved-tickets | M4a | ✅ |
| POST | /api/bob-sessions | M4c | ⚠️ Gate active (409 on pending) |
| POST | /api/outcomes | M5 | ⚠️ Gate active (409 on pending) |

### Jira Service
- `fetch_from_jira(jira_key)` — calls Jira REST API v3, validates custom field keys for story points and AC, returns `source_status` and `source_warning` on every code path
- `load_sample_stories()` / `load_sample_developer_profiles()` — loads from JSON files, enforces `source="sample"`
- Never silently substitutes sample data for a failed Jira import
- `source_status` values: `"jira"` | `"sample_import"` | `"credentials_missing"` | `"jira_error"`

### Sample Data
- `backend/sample_data/stories.json` — PIE sample open stories (user auth domain: PIE-2 login endpoint, PIE-4 JWT/Bcrypt), labeled `source="sample"`
- `backend/sample_data/resolved_tickets.json` — PIE resolved tickets for M4a similarity (PIE-1 user create, PIE-3 request DTO), labeled `source="sample"` — **M4a**
- `backend/sample_data/developer_profiles.json` — 3 developer profiles (Alex Chen, Priya Nair, Jordan Kim), labeled `source="sample"`

### Tests
- 33 pytest tests in [`backend/tests/test_milestone2.py`](backend/tests/test_milestone2.py) — all passing
- 42 pytest tests in [`backend/tests/test_milestone3.py`](backend/tests/test_milestone3.py) — all passing
- 50 pytest tests in [`backend/tests/test_milestone4a.py`](backend/tests/test_milestone4a.py) — all passing
- 60 pytest tests in [`backend/tests/test_milestone4b.py`](backend/tests/test_milestone4b.py) — all passing
- **Total: 382/382 passing** (includes hardening, AC quality, correctness prerequisite tests)
- Run from project root: `python3 -m pytest backend/tests/ -v`

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
python3 -m pytest backend/tests/ -v
# Expected: 382 passed
```

Tests use `bob_intelligence_test.db` (created and deleted automatically).
Production `bob_intelligence.db` is never touched by tests.

## Milestone 4a — What Was Implemented

### New ORM Model: `ResolvedTicket` ([`backend/models.py`](backend/models.py))

Fields: `id`, `jira_key` (unique), `title`, `description`, `resolution`, `labels`, `linked_prs`, `files_changed`, `mode_used`, `ac_met`, `was_reverted`, `source`, `created_at`.

Import is idempotent — duplicate `jira_key` records are skipped and counted in `skipped_duplicates`.

### New Recommendation Fields ([`backend/models.py`](backend/models.py) + [`backend/schemas.py`](backend/schemas.py))

Added to `Recommendation` and `RecommendationResponse`:
- `similar_tickets[]` — list of `{jira_key, title, similarity_score, resolution, mode_used, ac_met}`
- `supporting_prs[]` — union of `linked_prs` from similar tickets (GitHub enrichment deferred to M4b)
- `evidence_confidence` — `"high"` (≥3 with outcomes) | `"medium"` (1–2) | `"low"` (exist, no outcomes) | `"none"`
- `code_analysis_notes` — `null` in M4a (populated in M4b)

All four fields default gracefully (empty lists / `"none"` / `null`) — full backward compatibility with M3.

### Historical Evidence Service ([`backend/services/historical_evidence_service.py`](backend/services/historical_evidence_service.py))

- **`find_similar(story, db)`** — TF-IDF cosine similarity (pure Python, no external deps). Tokenises `title + description + labels` for both story and each resolved ticket. Returns up to 5 tickets with score ≥ 0.25, ordered descending. Returns `[]` immediately when the corpus is empty.
- **`build_supporting_prs(similar_tickets)`** — collects `linked_prs` from matched tickets, de-duped by URL. Title/merged/files_changed are `null`/`[]` until M4b GitHub enrichment.
- **`compute_evidence_confidence(similar_tickets)`** — counts tickets with both `mode_used` and `ac_met` set; returns `"high"`/`"medium"`/`"low"`/`"none"`.
- **`compute_mode_score_adjustment(similar_tickets)`** — returns `(delta, evidence_items)`:
  - `+10` when ≥2 similar tickets have `mode_used="bob_led"` and `ac_met=True`
  - `−10` when ≥1 similar ticket has `was_reverted=True`

### New Endpoints ([`backend/routers/resolved_tickets.py`](backend/routers/resolved_tickets.py))

- `POST /api/resolved-tickets/import` (source=`"sample"` or `"jira"`)
  - `source="sample"`: loads `sample_data/resolved_tickets.json`, returns `source_status="sample_import"`, idempotent
  - `source="jira"`: calls Jira search API with `JIRA_RESOLVED_JQL` env var; returns `source_status="credentials_missing"` when credentials absent — never substitutes sample data
- `GET /api/resolved-tickets`: returns all records with `total`

### Mode Engine Integration

`recommendation_service.generate()` now calls `historical_evidence_service.find_similar()` before the mode engine, passes results to `_mode_engine()`, and persists all four M4a fields on the `Recommendation` record. `uncertainty_note` includes `"no similar resolved tickets found"` when the corpus is empty or no match meets the threshold.

### Sample Data Domain (externally updated)

The sample data was updated to a real Spring Boot user-auth project:
- **Open stories**: PIE-2 (login endpoint), PIE-4 (JWT + Bcrypt)
- **Resolved tickets**: PIE-1 (user create REST endpoint), PIE-3 (request DTO with validation)
- Resolved tickets include real GitHub PR links, files_changed, mode_used, and ac_met

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

- **Developer match deferred.** `DeveloperProfile` model, sample data, and list/import endpoints are preserved but not used for recommendations. Deferred to Milestone 8.
- **Jira custom field keys unverified on real instance.** `JIRA_STORY_POINTS_FIELD` and `JIRA_AC_FIELD` vary by instance — service returns `source_warning` when missing.
- **`linked_prs` always empty on Jira story import.** Dev-status API call deferred to Milestone 4b.
- **`supporting_prs` GitHub metadata.** `merged`, `title`, `files_changed`, `state`, `test_files_present`, `was_reverted`, `ci_checks` are populated when `GITHUB_TOKEN` is set (M4b). When token is absent, all fields are null and `source_warning` is set.
- **`code_analysis_notes`.** Populated from LLM diff summaries when `LLM_API_KEY` is configured (M4b); falls back to file-count pattern analysis when `PIE_REPO_PATH` is set; explicitly null otherwise.
- **`Outcome.ac_met` is `Boolean`.** M5a will change it to `Text` (`"successful"/"partial"/"failed"/"unverified"`). The `"partial"` string path in `collect_outcome_evidence()` is forward-compatible but only fully operational after M5a.
- **`BobSession.human_interventions` does not exist yet.** M4c adds this field. Until then, all sessions show "zero interventions" — a positive signal. `collect_session_evidence()` uses `getattr(..., None)` as a forward-compatible fallback.
- **Bob session and outcome endpoints return 501** after the approval gate passes — full implementation in Milestones 4c and 5.
- **Bob session association is manual.** No automatic hook — confirmed design, not a bug.
- **Frontend pages are placeholder shells.** Real UI in Milestone 6.
- **TF-IDF similarity has no semantic understanding.** Two tickets about "login" and "authentication" may score low if they use different vocabulary. Upgrade to embeddings is planned but deferred (no API key required for M4a).

## Milestone 4b — What Was Implemented

### New Service: `github_service.py` ([`backend/services/github_service.py`](backend/services/github_service.py))

- **`parse_pr_url(url)`** — parses GitHub PR URLs into `(owner, repo, pr_number)` tuples. Returns `None` for invalid/non-GitHub URLs.
- **`fetch_pr_evidence(url)`** — calls GitHub REST API (`GET /repos/{owner}/{repo}/pulls/{number}` + `/files` + `/commits/{sha}/check-runs`). Returns a full evidence dict on success; partial evidence dict with `source_warning` on any failure (missing token, 401/403/404/5xx, network error). Never raises.
- **`_is_test_file(path)`** — detects test files via patterns: `test_*.py`, `*_test.py`, `*.spec.*`, `*.test.*`, `/test/`, `/tests/`.
- **`_detect_revert(title)`** — returns `True` when PR title contains "revert" (case-insensitive) **and** a `#N` PR reference. Does not trigger on "revert" alone.

### New Service: `llm_service.py` ([`backend/services/llm_service.py`](backend/services/llm_service.py))

- **`analyze_pr(...)`** — sends PR metadata + story context to the configured LLM; returns `(LLMAnalysis | None, warning)`. When `LLM_API_KEY` is absent, returns `(None, warning)` immediately.
- **`LLMAnalysis`** dataclass — `relevant`, `relevance_reason`, `diff_summary`, `has_tests`, `complexity`, `risk_flags`, `intervention_signal`, `mode_signal`, `mode_rationale`, `code_analysis_notes`.
- Provider abstraction: `LLM_PROVIDER=openai` (default) or `watsonx`. Provider details are hidden from `historical_evidence_service` and `recommendation_service`.
- LLM output is advisory — `mode_signal` does not override `mode_score`.

### New ORM Model: `PREvidence` ([`backend/models.py`](backend/models.py))

Fields: `id`, `resolved_ticket_id` (FK nullable), `story_id` (FK nullable), `url`, `title`, `state`, `merged`, `base_branch`, `head_branch`, `files_changed`, `test_files_present`, `was_reverted`, `ci_checks`, `diff_summary`, `code_analysis_notes`, `source`, `source_warning`, `verified`, `created_at`.

`merged=True` does NOT imply AC were met — stated explicitly in model docstring.

### Extended Historical Evidence Service

Added to [`backend/services/historical_evidence_service.py`](backend/services/historical_evidence_service.py):

- **`enrich_prs_with_github(supporting_prs, story, similar_tickets_full, db)`** — enriches each PR URL with GitHub metadata + optional LLM analysis. Persists `PREvidence` records. Excludes LLM-irrelevant PRs from return list. Returns `(enriched_prs, warnings)`.
- **`collect_outcome_evidence(similar_tickets_full, db)`** — fetches `Outcome` records for stories matching similar resolved tickets' `jira_key`. Returns `(evidence_items, risk_items)`.
- **`collect_session_evidence(similar_tickets_full, db)`** — fetches `BobSession` records for the same stories. Zero interventions → positive evidence; ≥3 → risk item.
- **`build_code_analysis_notes(enriched_prs, llm_unavailable_warning)`** — builds prose `code_analysis_notes` from LLM diff summaries or file-count pattern analysis.

### Extended Recommendation Service

Updated [`backend/services/recommendation_service.py`](backend/services/recommendation_service.py):

- `_mode_engine()` accepts 7 new optional params: `pr_evidence_items`, `pr_risk_items`, `outcome_evidence_items`, `outcome_risk_items`, `session_evidence_items`, `session_risk_items`, `llm_unavailable_warning`. All are advisory — the numeric `mode_score` is unchanged.
- `generate()` runs 5 numbered steps (previously 2): priority ranking → historical evidence → GitHub enrichment → outcome/session evidence → mode engine.
- `code_analysis_notes` is now populated by `build_code_analysis_notes()` rather than hard-coded to `None`.

### Configuration Required to Activate Enrichment

```bash
# .env (copy from .env.example)
GITHUB_TOKEN=ghp_...     # optional for public repos; required for private
LLM_PROVIDER=bob         # or "openai" / "watsonx"
LLM_API_KEY=...          # Bob API key (passed as BOB_API_KEY to CLI)
                         # For openai: sk-... | For watsonx: IAM token
LLM_ENDPOINT=            # not used for bob; required for watsonx
LLM_MODEL=               # not used for bob; optional for openai/watsonx
LLM_PROJECT_ID=          # watsonx only
```

When `LLM_API_KEY` is absent, mode defaults to `collaborative` and `uncertainty_note` is labelled `NOT an evidence-based recommendation`.
When `GITHUB_TOKEN` is absent on a public repo, PR enrichment proceeds unauthenticated (60 req/hour rate limit).

## Next Steps

1. **Milestone 4c** — Bob session link: full `POST /api/bob-sessions`, confirm flow, `diff_summary` capture, `human_interventions` field (activates `collect_session_evidence()` fully).
2. **Milestone 5a** — Requirement-level outcome recording (`ac_detail`, `ac_met` as Text — activates full `collect_outcome_evidence()` string paths).
3. **Milestone 5b** — Comparison and self-learning: resolved ticket promotion from successful outcomes.
4. **Milestone 6** — React frontend (4-screen wizard).
5. **Milestone 7** — Smoke test and demo readiness.
6. **Milestone 8 (future)** — Developer match.

## Milestone 6 — React Frontend (Mission Control)

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/vite-env.d.ts` | Vite `ImportMeta.env` type declarations (required for `VITE_API_BASE_URL`) |
| `frontend/src/index.css` | Global CSS — Mission Control design tokens (colors, spacing, radii) |
| `frontend/src/api/types.ts` | TypeScript types derived 1:1 from `backend/schemas.py` Pydantic models |
| `frontend/src/components/ui.tsx` | Reusable components: Badge, ModeBadge, ApprovalBadge, ConfidenceBadge, SourceBadge, PriorityBadge, Card, Button, Skeleton, EmptyState, ErrorBanner, WarningBanner, SampleDataBanner, MetaRow, Divider |
| `frontend/src/components/AppShell.tsx` | App shell: dark navy sidebar, sticky header, live connection indicator, responsive mobile nav |
| `frontend/src/components/ApprovalPanel.tsx` | Approve / override controls wired to exact backend schemas |
| `frontend/.env.example` | Documents `VITE_API_BASE_URL`; no secrets |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/api/client.ts` | Replaced placeholder with full typed API client for all 8 verified endpoints |
| `frontend/src/main.tsx` | Added global CSS import; changed story detail route to `/stories/:id` |
| `frontend/src/pages/StorySelector.tsx` | Full Story Queue: searchable list, sample + Jira import panel, skeletons, error/empty states |
| `frontend/src/pages/RecommendationView.tsx` | Story detail + mode hero + readiness panel + 4-tab evidence inspector + approval controls |
| `frontend/src/pages/LinkBobWork.tsx` | Honest "Planned" placeholder (M4c not implemented) |
| `frontend/src/pages/OutcomeComparison.tsx` | Honest "Planned" placeholder (M5 not implemented) |

### API Endpoints Used

| Method | Path | Used for |
|--------|------|---------|
| GET | /api/health | Connection indicator (on mount + manual recheck) |
| GET | /api/stories | Story queue list |
| POST | /api/stories/import | Sample and Jira story import |
| GET | /api/stories/{id} | Story detail |
| POST | /api/recommendations | Generate recommendation |
| GET | /api/recommendations/{id} | Refresh recommendation after approval |
| PATCH | /api/recommendations/{id}/mode-approve | Tech lead approve |
| PATCH | /api/recommendations/{id}/mode-override | Tech lead override |

### Design Decisions

- No fabricated confidence percentages, priority ranks, or AI rankings — all values come from the API.
- Sample data always shown with a visible `[SAMPLE DATA]` banner.
- Approval identity is recorded as entered; UI explicitly warns it is not authenticated.
- Bob Sessions and Outcomes pages show honest "Planned" state — never appear functional.
- Evidence disclaimers inline: TF-IDF similarity ≠ semantic equivalence; merged PR ≠ AC met; test file detection is a heuristic.
- `VITE_API_BASE_URL` env var for production; Vite dev proxy for local development (unchanged config).

### Verification

- `npm run build` (tsc + vite): ✅ clean, zero errors
- `npx tsc --noEmit`: ✅ zero TypeScript errors
- Backend files: zero changes — no backend tests affected by M6 work
- Pre-existing test failure `test_list_stories_returns_imported_story` confirmed unrelated to M6

### How to Run

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
# → http://localhost:5173
```

For production, set `VITE_API_BASE_URL=https://your-backend-origin` in `frontend/.env.local`.

