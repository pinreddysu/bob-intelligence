# Bob Intelligence — MVP Plan

## Top-Level Overview

**Goal:** Build a thin, demonstrable vertical slice that selects a Jira story, produces an explainable Bob/Collaborative/Human-led execution recommendation backed by evidence, links the story to real Bob-assisted work in the PIE repository, records verifiable engineering outcomes, and compares the original recommendation against the actual result.

**Scope:** Single-user, single-story demo. No auth, no multi-tenant, no org analytics.

**Approach:** Python + FastAPI backend with in-memory SQLite (via SQLAlchemy), React + TypeScript + Vite frontend, REST API. Recommendation logic is a pure rule engine behind a service interface. Jira calls use the REST v3 API; fall back to labeled sample data when credentials are absent.

**Runtime (confirmed):**
- Python 3.14.0b4 — pre-release; use only stable stdlib and dependency features, avoid anything marked provisional in 3.14 docs.
- Node v26.9.0 / npm 11.19.1 — current release, fully supported by Vite 5 and React 19.

**Frontend navigation:** Wizard-style (linear, step-by-step) — Story Selector → Recommendation → Link Bob Work → Outcome & Comparison.

**Sample story:** PIE-domain story pre-baked into the backend (e.g. "Add portfolio rebalancing endpoint to PIE API"). Always displayed with a visible `[SAMPLE DATA]` banner. Never presented as real engineering history.

**Out of scope for MVP:** developer rankings, story-point estimation, forecasting dashboards, microservices, background workers, automated Bob session telemetry.

---

## Repository Structure

```
bob-intelligence/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── database.py              # SQLAlchemy engine + session (in-memory SQLite)
│   ├── models.py                # ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── routers/
│   │   ├── stories.py           # /api/stories endpoints
│   │   ├── recommendations.py   # /api/recommendations endpoints
│   │   ├── bob_sessions.py      # /api/bob-sessions endpoints
│   │   └── outcomes.py          # /api/outcomes endpoints
│   ├── services/
│   │   ├── jira_service.py      # Jira REST v3 client + sample-data fallback
│   │   ├── recommendation_service.py  # Rule engine
│   │   └── evidence_service.py  # Git diff / test result capture helpers
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── StorySelector.tsx
│   │   │   ├── RecommendationView.tsx
│   │   │   ├── LinkBobWork.tsx
│   │   │   └── OutcomeComparison.tsx
│   │   ├── components/
│   │   ├── api/                 # Typed fetch wrappers
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── context.md
├── rules.md
├── BOB_USAGE.md
└── bob-intelligence-plan.md
```

---

## Architecture and Data Flow

```
Browser (React/Vite)
     │  REST JSON
     ▼
FastAPI (backend/main.py)
     ├── /api/stories         ──► jira_service  ──► Jira REST v3 API
     │                                           └─► sample_data.json (fallback)
     ├── /api/recommendations ──► recommendation_service (rule engine)
     ├── /api/bob-sessions    ──► SQLite (manual link + evidence)
     └── /api/outcomes        ──► evidence_service ──► Git CLI / test output files
                                                └─► SQLite
```

**No automatic Bob telemetry is assumed.** A Bob session is created explicitly by the user (or via a Bob hook later) and associated with a story ID.

---

## Core Entities

```
Story
  id                 TEXT PK
  jira_key           TEXT          -- e.g. PIE-42
  title              TEXT
  description        TEXT
  acceptance_criteria TEXT
  story_points       INT nullable
  labels             JSON
  source             TEXT          -- "jira" | "sample"
  created_at         DATETIME

Recommendation
  id                 TEXT PK
  story_id           TEXT FK → Story
  mode               TEXT          -- "bob_led" | "collaborative" | "human_led"
  rationale          TEXT          -- prose explanation
  evidence           JSON          -- list of evidence items
  risks              JSON
  counterevidence    JSON
  uncertainty_note   TEXT
  created_at         DATETIME
  status             TEXT          -- "pending" | "superseded"

BobSession
  id                 TEXT PK
  story_id           TEXT FK → Story
  summary            TEXT          -- manually entered description of Bob work
  files_changed      JSON          -- list of file paths
  pie_commit_sha     TEXT nullable -- git commit SHA in PIE repo
  created_at         DATETIME

Outcome
  id                 TEXT PK
  story_id           TEXT FK → Story
  bob_session_id     TEXT FK → BobSession nullable
  test_result        TEXT nullable -- "pass" | "fail" | "skipped"
  build_result       TEXT nullable -- "pass" | "fail"
  review_notes       TEXT nullable
  ac_met             BOOLEAN nullable
  diff_summary       TEXT nullable -- short prose of actual git diff
  created_at         DATETIME

Comparison
  id                 TEXT PK
  recommendation_id  TEXT FK → Recommendation
  outcome_id         TEXT FK → Outcome
  verdict            TEXT          -- "confirmed" | "exceeded" | "diverged"
  explanation        TEXT
  created_at         DATETIME
```

---

## REST Endpoints (Minimum Viable)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/stories | List imported stories |
| POST | /api/stories/import | Import story from Jira or create sample |
| GET | /api/stories/{id} | Get single story |
| POST | /api/recommendations | Generate recommendation for a story |
| GET | /api/recommendations/{id} | Get recommendation |
| POST | /api/bob-sessions | Create Bob session link |
| GET | /api/bob-sessions/{story_id} | Get sessions for a story |
| POST | /api/outcomes | Record outcome for a story |
| GET | /api/outcomes/{story_id} | Get outcome for a story |
| POST | /api/comparisons | Generate recommendation vs outcome comparison |
| GET | /api/comparisons/{story_id} | Get comparison for a story |
| GET | /api/health | Liveness check |

---

## Frontend Screens

| Screen | Route | Purpose |
|--------|-------|---------|
| Story Selector | `/` | Enter Jira key or pick sample story; trigger import |
| Recommendation View | `/stories/:id/recommendation` | Show mode, rationale, evidence, risks, uncertainty |
| Link Bob Work | `/stories/:id/bob-session` | Manually attach Bob session summary, files, commit SHA |
| Outcome & Comparison | `/stories/:id/outcome` | Enter test/build results, AC met; show comparison |

Navigation is linear (wizard-style) for demo clarity.

---

## Explainable Recommendation Approach

The recommendation engine scores a story against a fixed set of transparent rules. No probabilities are invented.

**Input signals (what the engine reads):**
- Story point count (if present)
- Description length and structure
- Presence of acceptance criteria
- Label keywords (e.g. "infrastructure", "security", "ui", "refactor")
- Number of open unknowns detected in description text
- Historical comparisons stored in the DB (zero at first run — engine notes this explicitly)

**Rule categories:**
- **Complexity signals** → favor Human-led when story points are high or description contains many open questions
- **Routine/pattern signals** → favor Bob-led when story matches known low-risk patterns (CRUD, config, test scaffolding)
- **Risk signals** → flag security/infra labels; push toward Human-led or Collaborative
- **Evidence availability** → if no historical outcomes exist, uncertainty_note is set and confidence is reduced

**Output:** `mode` + `rationale` string + `evidence[]` + `risks[]` + `counterevidence[]` + `uncertainty_note`.

The service interface (`RecommendationService.generate(story) → Recommendation`) is kept clean so an LLM or watsonx call can replace or augment the rule engine later without changing the API layer.

---

## Jira Integration

**Approach:** Wire the live Jira REST v3 API. Fall back to sample data when credentials are absent. Sample data is always labeled `source: "sample"` and displayed with a visible banner.

**Required credentials (`.env`):**
- `JIRA_BASE_URL` — e.g. `https://yourorg.atlassian.net`
- `JIRA_USER_EMAIL`
- `JIRA_API_TOKEN` — generated at id.atlassian.com

**Minimum permission needed:** Read access to the project containing the story.

**Fields fetched:** summary, description, story points (custom field), labels, acceptance criteria (description body or custom field depending on instance config).

**Unknowns to validate cheaply:**
- Acceptance criteria field name varies by Jira configuration. Validate by fetching one known story and inspecting all returned fields before writing the parser.
- Story point custom field key (`customfield_10016` is common but not universal). Validate the same way.
- Atlassian Cloud vs Server API path differences. Assume Cloud for MVP.

**Validation approach:** A single `GET /rest/api/3/issue/{key}?expand=names` call on a known story reveals all field names and values. Run this once manually during integration and record the field keys in `.env` or config.

---

## IBM Bob Integration

**Confirmed:** Bob does not expose session-history APIs, telemetry, or token-usage capture automatically.

**Approach:** Explicit association. A user (or a Bob lifecycle hook added later) creates a `BobSession` record by posting to `/api/bob-sessions` with:
- The story ID
- A summary of what Bob helped with
- The list of files changed
- Optionally, the PIE commit SHA

**What can be automatically captured (with a Bob hook):** The `stop` or `session_end` hook can POST to `/api/bob-sessions` with files changed during the session, if Bob exposes changed-file metadata. This is listed as a stretch goal and must be validated before being claimed as working.

**What is never fabricated:** token counts, automated outcome quality scores, or AI contribution percentages.

---

## Git and Verification Evidence

**Approach:** When a `BobSession` includes a `pie_commit_sha`, the backend calls `git show --stat <sha>` in the PIE repo path (configured via `PIE_REPO_PATH` env var) to produce a `diff_summary`. This is stored in the `Outcome` record.

**Test results:** The user pastes or uploads a short test result string. The `evidence_service` can optionally read a `pytest` JSON output file if `PIE_TEST_RESULT_PATH` is set.

**Constraint:** Automatic capture is only claimed after the file-read or git command is verified to work in the demo environment.

---

## Testing Strategy

- **Backend:** `pytest` with `httpx.AsyncClient` against the FastAPI app using an in-memory SQLite DB. Cover the happy path for each endpoint and the three recommendation rule branches.
- **Frontend:** No unit tests required for MVP. Manual walkthrough against the running backend is sufficient for the demo.
- **Integration smoke test:** A `scripts/smoke_test.sh` that imports the sample story, generates a recommendation, creates a Bob session, records an outcome, and prints the comparison — all via `curl`. Runs without credentials.

---

## Documentation Maintenance

**`context.md`:** Updated after each milestone is completed. Contains: product goal, stack, architecture summary, current implementation status, key decisions with rationale, known limitations, and next steps.

**`rules.md`:** Updated only when a persistent Bob instruction needs to change. Contains the constraints listed in section 6 of the product brief.

**`BOB_USAGE.md`:** Updated after each meaningful Bob task is completed and results are verified. Each entry: entry number, date, objective, prompt summary, files created/modified (actual), what was implemented vs proposed, verification performed, actual results, limitations, value delivered.

---

## Implementation Milestones

### Milestone 1 — Scaffold and documentation baseline
**Acceptance criteria:**
- Repository structure exists with empty placeholder files.
- `context.md`, `rules.md`, `BOB_USAGE.md` created with initial content.
- Backend `requirements.txt` and `frontend/package.json` present with correct dependencies.
- `GET /api/health` returns `{"status": "ok"}`.
- Status: `[x] complete` — verified 2025-07-14. Health endpoint returns 200. Smoke test exits 0.

### Milestone 2 — Data layer and story import
**Acceptance criteria:**
- All five ORM models exist and create tables on startup.
- `POST /api/stories/import` with `source=sample` creates a story labeled `source: "sample"`.
- `POST /api/stories/import` with a Jira key calls the Jira API when credentials are present, falls back to sample data with a `source: "sample"` flag and a visible warning when they are absent.
- `GET /api/stories` returns the imported story.
- Status: `[ ] pending`

### Milestone 3 — Recommendation engine
**Acceptance criteria:**
- `POST /api/recommendations` with a story ID returns a recommendation with `mode`, `rationale`, `evidence`, `risks`, `counterevidence`, and `uncertainty_note`.
- All three modes are reachable via different story inputs (validated by the pytest suite).
- When no historical outcomes exist, `uncertainty_note` explicitly states this.
- Status: `[ ] pending`

### Milestone 4 — Bob session link and evidence capture
**Acceptance criteria:**
- `POST /api/bob-sessions` stores a session with summary, files, and optional commit SHA.
- When a commit SHA and `PIE_REPO_PATH` are set, the backend runs `git show --stat` and stores the diff summary.
- `GET /api/bob-sessions/{story_id}` returns the session.
- Status: `[ ] pending`

### Milestone 5 — Outcome recording and comparison
**Acceptance criteria:**
- `POST /api/outcomes` stores test result, build result, review notes, and AC met flag.
- `POST /api/comparisons` produces a `verdict` and `explanation` comparing the original recommendation mode to the actual outcome.
- `GET /api/comparisons/{story_id}` returns the comparison.
- Status: `[ ] pending`

### Milestone 6 — React frontend
**Acceptance criteria:**
- Four screens exist and navigate in wizard order.
- Story Selector shows a sample-data banner when `source === "sample"`.
- Recommendation View renders mode badge, rationale, evidence list, risks, counterevidence, uncertainty note.
- Link Bob Work form submits and confirms.
- Outcome & Comparison screen shows the verdict and explanation side by side.
- App runs via `npm run dev` and connects to the local backend.
- Status: `[ ] pending`

### Milestone 7 — Smoke test and demo readiness
**Acceptance criteria:**
- `scripts/smoke_test.sh` runs end-to-end without credentials and exits 0.
- `BOB_USAGE.md` has at least one complete entry reflecting real implemented work.
- `context.md` reflects the final implementation state.
- Demo walkthrough (manual) matches the definition of done below.
- Status: `[ ] pending`

---

## Definition of Done — First End-to-End Demo

1. User opens the app and selects the sample story (labeled as sample).
2. App calls the backend; story is stored; recommendation is generated and displayed with mode, evidence, risks, and uncertainty note.
3. User notes the recommendation is saved before any work begins.
4. User enters a Bob session summary, lists files changed in PIE, and optionally provides a commit SHA.
5. Backend fetches the git diff summary (if SHA provided) and stores it.
6. User enters the actual test/build result and whether AC were met.
7. App displays the comparison: original recommendation vs actual outcome, with verdict and explanation.
8. User navigates back — the record persists for the session.
9. Demo clearly distinguishes what is implemented (all of the above) from what is not yet automated (Bob hook, live Jira if no credentials).

---

## Single Best First Task

**Milestone 1 — Scaffold and documentation baseline.**

It is dependency-free, takes one focused Bob session, produces the structure every subsequent task depends on, and immediately generates a real `BOB_USAGE.md` entry. All later milestones reference paths and module names established here.
