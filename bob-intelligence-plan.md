# Bob Intelligence — MVP Plan

## Top-Level Overview

**Goal:** Build a thin, demonstrable vertical slice that:
1. **Prioritizes** which open Jira ticket the team should work on next, based on priority, blockers, readiness, risk, and available context.
2. **Recommends an execution mode** — Bob-led, Collaborative (human + Bob), or Human-led — backed by evidence for the selected ticket.
3. ~~**Suggests a developer match**~~ — **DEFERRED to a future phase.** Developer ranking, skill verification, team matching, and GitHub/Jira bootstrap integration are out of scope for the current MVP. The `DeveloperProfile` model and sample data are preserved for future use. The `Outcome.developer_id` FK is kept so actual developer can be recorded against an outcome without requiring a match recommendation.

Both active recommendations are evidence-backed with explicit rationale, risk, missing evidence, and uncertainty. A tech lead must approve or override the execution-mode recommendation before work begins. No evidence is invented and no developer is ranked by AI activity.

**Scope:** Single-user, single-story demo. No auth, no multi-tenant, no org analytics.

**Approach:** Python + FastAPI backend with file-backed SQLite (via SQLAlchemy, `bob_intelligence.db`), React + TypeScript + Vite frontend, REST API. Recommendation logic is a pure rule engine behind a service interface. Jira calls use the REST v3 API. When Jira credentials are absent or a Jira request fails, the response includes an explicit `source_status` warning and the caller must display a visible error; sample data is never silently substituted.

**Runtime (confirmed):**
- Python 3.14.0b4 — pre-release; use only stable stdlib and dependency features, avoid anything marked provisional in 3.14 docs.
- Node v26.9.0 / npm 11.19.1 — current release, fully supported by Vite 5 and React 19.

**Frontend navigation:** Wizard-style (linear, step-by-step) — Ticket Prioritization → Execution Mode → Link Bob Work → Outcome & Comparison.

**Sample story:** PIE-domain story pre-baked into the backend (e.g. "Add portfolio rebalancing endpoint to PIE API"). Always displayed with a visible `[SAMPLE DATA]` banner. Never presented as real engineering history. Sample developer profiles are preserved in `sample_data/` and the DB model exists, but are not used for recommendations in this phase.

**Out of scope for current MVP:** developer match recommendations, developer ranking by any signal, skill verification, team matching, GitHub/Jira PR bootstrap, story-point estimation, forecasting dashboards, microservices, background workers, automated Bob session telemetry.

**Deferred to a future phase:** Decision 3 (Developer Match) — full design in the "Three Decisions" section below, marked deferred.

---

## Repository Structure

```
bob-intelligence/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── database.py              # SQLAlchemy engine + session (file-backed SQLite: bob_intelligence.db)
│   ├── models.py                # ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── routers/
│   │   ├── stories.py           # /api/stories endpoints
│   │   ├── recommendations.py   # /api/recommendations endpoints (mode + priority + dev match)
│   │   ├── bob_sessions.py      # /api/bob-sessions endpoints
│   │   └── outcomes.py          # /api/outcomes endpoints
│   ├── services/
│   │   ├── jira_service.py      # Jira REST v3 client + sample-data fallback
│   │   ├── recommendation_service.py  # Rule engine: priority, mode, dev match
│   │   ├── dev_profile_service.py     # Developer profile loader + evidence aggregator
│   │   └── evidence_service.py  # Git diff / test result capture helpers
│   ├── sample_data/
│   │   ├── stories.json         # [SAMPLE DATA] labeled stories
│   │   └── developer_profiles.json  # [SAMPLE DATA] labeled developer profiles
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── TicketPrioritization.tsx    # NEW — step 1 of wizard
│   │   │   ├── RecommendationView.tsx      # execution mode (step 2)
│   │   │   ├── DeveloperMatch.tsx          # NEW — step 3 of wizard
│   │   │   ├── LinkBobWork.tsx
│   │   │   └── OutcomeComparison.tsx
│   │   ├── components/
│   │   │   ├── SampleDataBanner.tsx        # Reusable [SAMPLE DATA] banner
│   │   │   ├── EvidenceList.tsx            # Reusable evidence + uncertainty display
│   │   │   └── ApprovalGate.tsx            # "Tech lead must approve" gate widget
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
     ├── /api/stories              ──► jira_service  ──► Jira REST v3 API
     │                                                └─► sample_data/stories.json (explicit sample import)
     ├── /api/recommendations      ──► recommendation_service
     │                                   ├── priority_engine     (ticket prioritization)
     │                                   └── mode_engine         (Bob/Collab/Human)
     │                                   [dev_match_engine DEFERRED]
     ├── /api/bob-sessions         ──► SQLite (manual link + evidence)
     └── /api/outcomes             ──► evidence_service ──► Git CLI / test output files
                                                     └─► SQLite
```

**No automatic Bob telemetry is assumed.** A Bob session is created explicitly by the user (or via a Bob hook later) and associated with a story ID.

**Recommendation approval gate:** The execution-mode recommendation carries `mode_approval_status: "pending"`. A tech lead PATCH confirms or overrides before work is assigned. The system never auto-assigns work. Developer-match approval gate is deferred with the developer-match feature.

---

## Core Entities

```
Story
  id                 TEXT PK
  jira_key           TEXT          -- e.g. PIE-42
  title              TEXT
  description        TEXT
  acceptance_criteria TEXT
  story_points       INT nullable  -- imported metadata only; MUST NOT influence recommendations or prioritization
  labels             JSON
  priority           TEXT nullable  -- "highest" | "high" | "medium" | "low" | "lowest"
  status             TEXT nullable  -- Jira workflow status (e.g. "To Do", "In Progress")
  assignee           TEXT nullable  -- current Jira assignee (raw, not a DeveloperProfile FK)
  blockers           JSON           -- list of blocking issue keys
  linked_prs         JSON           -- list of PR URLs linked in Jira
  source             TEXT          -- "jira" | "sample"
  created_at         DATETIME

Recommendation
  id                 TEXT PK
  story_id           TEXT FK → Story
  -- Ticket prioritization
  priority_rank      INT nullable   -- relative rank among open tickets (1 = highest)
  priority_rationale TEXT nullable  -- why this ticket surfaces first
  priority_evidence  JSON           -- blockers cleared, sprint goals, dependency chains
  -- Execution mode
  mode               TEXT          -- "bob_led" | "collaborative" | "human_led"
  mode_rationale     TEXT          -- prose explanation
  mode_evidence      JSON          -- list of evidence items supporting mode choice
  mode_risks         JSON
  mode_counterevidence JSON
  mode_approval_status TEXT        -- "pending" | "approved" | "overridden"  (independent gate)
  mode_approved_by   TEXT nullable  -- tech lead identifier
  mode_approved_at   DATETIME nullable
  mode_override_reason TEXT nullable -- required (non-empty) when mode_approval_status="overridden"
  -- Developer match fields (DEFERRED — model columns preserved for future phase)
  -- suggested_developer, dev_match_*, is_stretch_assignment, stretch_support_plan,
  -- dev_match_approval_status, dev_match_approved_by, dev_match_approved_at,
  -- dev_match_override_reason are in the ORM model but NOT populated or used in MVP.
  -- Shared
  uncertainty_note   TEXT           -- explicit statement of missing evidence
  created_at         DATETIME
  status             TEXT          -- "pending" | "superseded"

DeveloperProfile
  id                 TEXT PK
  display_name       TEXT
  jira_account_id    TEXT nullable  -- used to correlate Jira assignee fields
  verified_skills    JSON           -- list of skill tags drawn from verified evidence only
  verified_pr_count  INT            -- count of merged PRs with evidence in this system
  verified_review_count INT         -- count of code reviews recorded
  recent_domains     JSON           -- e.g. ["api", "frontend", "infra"] from recent work
  availability_note  TEXT nullable  -- optional free-text (e.g. "on leave week 3")
  source             TEXT           -- "jira" | "sample"
  -- NOTE: No AI-activity score, no seniority inferred from activity count

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
  developer_id       TEXT FK → DeveloperProfile nullable  -- who actually did the work
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
  -- Mode comparison
  mode_verdict       TEXT          -- "confirmed" | "exceeded" | "diverged"
  mode_explanation   TEXT
  -- Dev match comparison (DEFERRED — columns preserved, not populated in MVP)
  dev_match_verdict  TEXT nullable -- "matched" | "overridden" | "stretch_succeeded" | "stretch_failed" | "no_match_recorded"
  dev_match_explanation TEXT nullable
  created_at         DATETIME
```

---

## REST Endpoints (Minimum Viable)

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | /api/health | Liveness check | ✅ MVP |
| GET | /api/stories | List imported stories with priority, status, blockers | ✅ MVP |
| POST | /api/stories/import | Import story from Jira or from sample data | ✅ MVP |
| GET | /api/stories/{id} | Get single story | ✅ MVP |
| GET | /api/developer-profiles | List developer profiles | ✅ MVP |
| POST | /api/developer-profiles/import-sample | Import sample developer profiles | ✅ MVP |
| POST | /api/recommendations | Generate priority + execution-mode recommendations for a story | MVP (Milestone 3) |
| GET | /api/recommendations/{id} | Get recommendation (priority + mode) | MVP (Milestone 3) |
| PATCH | /api/recommendations/{id}/mode-approve | Tech lead approves execution mode; requires non-empty `approved_by` | MVP (Milestone 3) |
| PATCH | /api/recommendations/{id}/mode-override | Tech lead overrides; requires `approved_by` + `override_reason`; 422 if missing | MVP (Milestone 3) |
| POST | /api/bob-sessions | Create Bob session link | MVP (Milestone 4) |
| GET | /api/bob-sessions/{story_id} | Get sessions for a story | MVP (Milestone 4) |
| POST | /api/outcomes | Record outcome for a story | MVP (Milestone 5) |
| GET | /api/outcomes/{story_id} | Get outcome for a story | MVP (Milestone 5) |
| POST | /api/comparisons | Generate mode recommendation vs outcome comparison | MVP (Milestone 5) |
| GET | /api/comparisons/{story_id} | Get comparison for a story | MVP (Milestone 5) |
| POST | /api/developer-profiles | Create or upsert a developer profile | DEFERRED |
| POST | /api/recommendations/{id}/dev-match-approve | Developer match approval gate | DEFERRED |
| POST | /api/recommendations/{id}/dev-match-override | Developer match override | DEFERRED |

---

## Frontend Screens

| Screen | Route | Purpose | Status |
|--------|-------|---------|--------|
| Ticket Prioritization | `/` | Show open tickets ranked by priority engine; select the next ticket to work on | MVP |
| Execution Mode | `/stories/:id/recommendation` | Show Bob/Collaborative/Human-led mode, rationale, evidence, risks, uncertainty, approval gate | MVP |
| Link Bob Work | `/stories/:id/bob-session` | Manually attach Bob session summary, files, commit SHA | MVP |
| Outcome & Comparison | `/stories/:id/outcome` | Enter test/build results, AC met; show mode comparison vs original recommendation | MVP |
| Developer Match | `/stories/:id/developer` | Show suggested developer, rationale, evidence, stretch flag, approval gate | **DEFERRED** |

Navigation is linear (wizard-style) for demo clarity. The `ApprovalGate` component blocks progression past the Execution Mode screen until a tech lead confirms or overrides. The Developer Match screen is deferred.

---

## Three Decisions — Design Detail

### Decision 1: Ticket Prioritization

**Purpose:** Surface the single best next ticket from a list of open stories.

**Input signals:**
- Jira `priority` field (Highest → Lowest)
- Presence and count of blocking issues (`blockers[]`)
- Story `status` (e.g. "Ready for Dev" ranks above "Backlog")
- Acceptance criteria completeness (present and non-empty = more ready)
- Label keywords indicating risk or urgency (e.g. "security", "p0", "incident")
- Dependency chains inferred from linked issues (where available in Jira response)
- Number of open unknowns detected in description text (same signal as mode engine)

**Explicitly excluded from prioritization:**
- `story_points` — story-point estimation is out of scope for MVP; existing Jira story-point values are displayed as imported metadata only and must not influence priority rank or any recommendation.
- Historical success patterns — no such verified outcome records exist at first run; if `Outcome` records accumulate later, they may be considered in a future iteration, but the engine must not claim historical signal when none exists. When fewer than three `Outcome` records exist, `uncertainty_note` states this explicitly.

**Output fields added to `Recommendation`:** `priority_rank`, `priority_rationale`, `priority_evidence[]`

**Uncertainty:** If only sample data is available, `uncertainty_note` states this explicitly. The engine never fabricates urgency or invents historical patterns.

**Constraint:** Priority rank is advisory. It informs the tech lead's ticket selection but does not enforce it. No separate approval gate or prioritization approval endpoint exists in the MVP. The tech lead explicitly selects a story from the ranked list, and the system then generates its execution-mode recommendation. The execution-mode approval gate must be passed before downstream Bob-session and outcome operations can proceed.
---

### Decision 2: Execution Mode

**Purpose:** Recommend whether the selected ticket should be Bob-led, Collaborative, or Human-led.

**Input signals:**
- Description length and structure
- Presence of acceptance criteria
- Label keywords (e.g. "infrastructure", "security", "ui", "refactor")
- Number of open unknowns detected in description text
- Historical `Comparison` records in DB — used only when records exist; when none exist, `uncertainty_note` states "no historical outcomes available" and confidence is reduced accordingly
- `blockers[]` — unresolved blockers push toward Human-led (human judgment needed)
- `linked_prs` — presence of prior PR context can support Collaborative or Bob-led

**Rule categories (unchanged):**
- **Complexity signals** → favor Human-led when description contains many open questions or unresolved unknowns
- **Routine/pattern signals** → favor Bob-led when story matches known low-risk patterns (CRUD, config, test scaffolding)
- **Risk signals** → flag security/infra labels; push toward Human-led or Collaborative
- **Evidence availability** → if no historical outcomes exist, uncertainty_note is set and confidence is reduced

**Output:** `mode` + `mode_rationale` + `mode_evidence[]` + `mode_risks[]` + `mode_counterevidence[]` + `uncertainty_note`

---

### Decision 3: Developer Match — DEFERRED

> **Status: deferred to a future phase.** The `DeveloperProfile` ORM model, sample data in `sample_data/developer_profiles.json`, the `GET /api/developer-profiles` and `POST /api/developer-profiles/import-sample` endpoints, and all `dev_match_*` columns on `Recommendation` are preserved in the codebase. They are not populated or used by the recommendation engine in the current MVP.
>
> The design below is retained as the specification for when this phase is resumed.

**Purpose:** Suggest the best-fit developer for the ticket, or flag a stretch assignment with a support plan.

**Bootstrap path (future):** Jira dev-status API (`/rest/dev-status/1.0/`) retrieves merged PR links from resolved tickets assigned to a developer. File paths from merged PRs map to skill/domain candidates. Author and reviewer counts from merged PRs populate `verified_pr_count` and `verified_review_count`. All inferences require human confirmation before writing to the profile. This path requires Jira Cloud with GitHub/GitLab integration; fallback is GitHub API (`api.github.com`) using `GITHUB_TOKEN` for manual PR links.

**Cold-start behaviour (future):** At first run with empty profiles the engine returns `suggested_developer: null` and an explicit `uncertainty_note`. As `Outcome` records with `ac_met=true` and `developer_id` accumulate, the engine gains real signal and confidence improves.

**Input signals:**
- `DeveloperProfile.verified_skills[]` — drawn only from verified evidence (merged PRs, recorded reviews, passed outcomes) in this system. Never inferred from activity count alone.
- `DeveloperProfile.recent_domains[]` — domain overlap with story labels
- `DeveloperProfile.verified_pr_count` / `verified_review_count` — used only to confirm familiarity, not to rank
- `DeveloperProfile.availability_note` — optional signal; absence does not imply unavailability
- Story `labels`, `description`, and `acceptance_criteria` — to identify required domain knowledge
- Historical `Outcome` records — which developers have completed similar stories with AC met

**Matching logic:**
1. Find developers whose `verified_skills` and `recent_domains` overlap with the story's domain signals.
2. Among those, prefer developers with at least one prior `Outcome` where `ac_met = true` for a similar story.
3. If no strong match exists, flag `is_stretch_assignment = true` and populate `stretch_support_plan`.
4. If evidence is insufficient, `suggested_developer` is null and `uncertainty_note` states what is missing.

**Hard constraints (non-negotiable, apply when this phase is built):**
- No developer is ranked by volume of AI tool usage or Bob session count.
- Missing experience with a domain is stated as "no verified evidence of X in this system" — never as "cannot do X".
- The system never auto-assigns. `dev_match_approval_status` must be set to `"approved"` or `"overridden"` by a tech lead.
- `DeveloperProfile` records sourced from sample data carry `source: "sample"` and are shown with a `[SAMPLE DATA]` banner.

**Output (future):** `suggested_developer`, `dev_match_rationale`, `dev_match_evidence[]`, `dev_match_risks[]`, `is_stretch_assignment`, `stretch_support_plan`, `uncertainty_note`

---

## Explainable Recommendation Approach

The recommendation engine scores a story against a fixed set of transparent rules. No probabilities are invented.

The `RecommendationService.generate(story, developer_profiles) → Recommendation` interface is kept clean so an LLM or watsonx call can replace or augment any of the three sub-engines later without changing the API layer.

**Shared output envelope for all three decisions:**
```
rationale:         prose explanation
evidence[]:        list of {source, description, verified: bool}
risks[]:           list of {description, severity: "low"|"medium"|"high"}
counterevidence[]: list of {description}  -- evidence that cuts against the recommendation
uncertainty_note:  explicit prose about what evidence is absent
```

`verified: false` items are surfaced to the user and labeled "unverified signal" — they inform but are never the sole basis for a recommendation.

---

## Jira Integration

**Approach:** Wire the live Jira REST v3 API. When credentials are absent or a Jira request fails, the backend returns an explicit `source_status` field (e.g. `"jira_unavailable"`, `"credentials_missing"`, `"jira_error"`) along with a human-readable `source_warning` message. The frontend must display this warning visibly. Sample data is always labeled `source: "sample"` and displayed with a `[SAMPLE DATA]` banner. Sample data is never silently substituted for a failed live Jira request.

**Required credentials (`.env`):**
- `JIRA_BASE_URL` — e.g. `https://yourorg.atlassian.net`
- `JIRA_USER_EMAIL`
- `JIRA_API_TOKEN` — generated at id.atlassian.com

**Minimum permission needed:** Read access to the project containing the story.

**Fields fetched:** summary, description, story points (custom field — stored as imported metadata only, not used for recommendations), labels, acceptance criteria (description body or custom field depending on instance config), priority, status, blocking links, linked PRs (via remotelinks or issuelinks).

**Unknowns to validate cheaply:**
- Acceptance criteria field name varies by Jira configuration. Validate by fetching one known story and inspecting all returned fields before writing the parser.
- Story point custom field key (`customfield_10016` is common but not universal). Validate the same way.
- Atlassian Cloud vs Server API path differences. Assume Cloud for MVP.
- Blocker link type name (`is blocked by` vs `blocks`) varies by instance. Validate once.

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

**What is never fabricated:** token counts, automated outcome quality scores, AI contribution percentages, or developer skill inferences from Bob session frequency.

---

## Git and Verification Evidence

**Approach:** When a `BobSession` includes a `pie_commit_sha`, the backend calls `git show --stat <sha>` in the PIE repo path (configured via `PIE_REPO_PATH` env var) to produce a `diff_summary`. This is stored in the `Outcome` record.

**Test results:** The user pastes or uploads a short test result string. The `evidence_service` can optionally read a `pytest` JSON output file if `PIE_TEST_RESULT_PATH` is set.

**Developer evidence aggregation:** `dev_profile_service` can optionally read linked PR metadata from the Jira response to populate `linked_prs` on a story, but no automated skill inference is performed — a human must review and confirm before a skill is added to a `DeveloperProfile`.

**Constraint:** Automatic capture is only claimed after the file-read or git command is verified to work in the demo environment.

---

## Testing Strategy

- **Backend:** `pytest` with `httpx.AsyncClient` against the FastAPI app. Tests use a separate isolated test database (`bob_intelligence_test.db`), created fresh at test session start and deleted on teardown — configured via a `conftest.py` fixture that overrides the `DATABASE_URL` setting. Production `bob_intelligence.db` is never touched by tests.

  **Required test cases (in addition to happy-path endpoint coverage):**
  - Database persistence: write a `Story` and `Recommendation` record, close and reopen the DB session, confirm records are retrievable — verifying file-backed persistence across simulated restarts.
  - Failed Jira import: call `POST /api/stories/import` with a Jira key but no credentials set; assert the response includes `source_status: "credentials_missing"` and a non-empty `source_warning`; assert no silent fallback to sample data without the warning.
  - Sample-data labeling: assert every `Story` and `DeveloperProfile` created from sample data has `source: "sample"`.
  - Approval enforcement: assert that `POST /api/recommendations` creates a record with `mode_approval_status: "pending"`; assert that `POST /api/bob-sessions` and `POST /api/outcomes` return 409 when `mode_approval_status` is still `"pending"`. Ticket priority rank has no approval gate and must not be tested as one.
  - Override reason required: call `PATCH /api/recommendations/{id}/mode-override` with an empty or missing `override_reason`; assert the request is rejected with a 422.
  - Reviewer and timestamp recorded: after a successful `mode-approve` or `mode-override` call, assert `mode_approved_by` is non-null and `mode_approved_at` is a valid ISO timestamp.
  - Story-point isolation: assert the priority engine output is identical whether or not `story_points` is populated on the input story.

- **Frontend:** No unit tests required for MVP. Manual walkthrough against the running backend is sufficient for the demo.
- **Integration smoke test:** A `scripts/smoke_test.sh` that imports the sample story, generates priority + execution-mode recommendations, explicitly approves the execution-mode decision via `curl PATCH .../mode-approve` (simulating tech lead approval), asserts that the override failure path (`/mode-override` with missing `override_reason`) returns 422, creates a Bob session, records an outcome, and prints the comparison — all via `curl`. Runs without credentials.

---

## Documentation Maintenance

**`context.md`:** Updated after each milestone is completed. Contains: product goal, stack, architecture summary, current implementation status, key decisions with rationale, known limitations, and next steps.

**`rules.md`:** Updated only when a persistent Bob instruction needs to change. Contains the constraints listed in section 6 of the product brief.

**`BOB_USAGE.md`:** Updated after each meaningful Bob task is completed and results are verified. Each entry: entry number, date, objective, prompt summary, files created/modified (actual), what was implemented vs proposed, verification performed, actual results, limitations, value delivered.

---

## Implementation Milestones

### Milestone 1 — Scaffold and documentation baseline
**Acceptance criteria:**
- Repository structure exists with empty placeholder files including `sample_data/` directory.
- `context.md`, `rules.md`, `BOB_USAGE.md` created with initial content.
- Backend `requirements.txt` and `frontend/package.json` present with correct dependencies.
- `GET /api/health` returns `{"status": "ok"}`.
- Status: `[x] complete` — verified 2025-07-14. Health endpoint returns 200. Smoke test exits 0.

### Milestone 2 — Data layer and story import
**Acceptance criteria:**
- All ORM models exist (`Story`, `Recommendation`, `DeveloperProfile`, `BobSession`, `Outcome`, `Comparison`) and create tables on startup against `bob_intelligence.db` (file-backed).
- `POST /api/stories/import` with `source=sample` creates a story labeled `source: "sample"` with `priority`, `status`, `blockers`, and `linked_prs` fields populated from sample data. `story_points` is populated if present in sample data but is treated as display-only metadata.
- `POST /api/stories/import` with a Jira key and valid credentials calls the Jira API and returns `source_status: "jira"`. When credentials are absent or the Jira request fails, the response returns `source_status: "credentials_missing"` or `source_status: "jira_error"` and a non-empty `source_warning`; the caller must surface this warning visibly; sample data is never silently substituted without the warning.
- `GET /api/stories` returns imported stories with priority, status, blockers, and `source` fields.
- `GET /api/developer-profiles` returns developer profiles labeled `source: "sample"` (or `source: "jira"` if imported).
- Sample data is stored in `sample_data/stories.json` and `sample_data/developer_profiles.json`, clearly labeled, never silently substituted.
- Records written in this milestone persist across backend process restarts (verified by stopping and restarting the server and calling `GET /api/stories`).
- pytest persistence test passes (see Testing Strategy).
- Status: `[x] complete` — verified 2025-07-15. 33/33 tests passing. Smoke test exits 0.

### Milestone 3 — Recommendation engine (priority + execution mode)
**Acceptance criteria:**
- `POST /api/recommendations` with a story ID returns a recommendation record containing: `priority_rank` + `priority_rationale` + `priority_evidence`; `mode` + `mode_rationale` + `mode_evidence` + `mode_risks` + `mode_counterevidence`; shared `uncertainty_note`.
- Developer-match fields (`suggested_developer`, `dev_match_*`, `is_stretch_assignment`, etc.) are present in the model but **not populated** by this milestone — they remain null/empty and are not tested here.
- All three execution modes are reachable via different story inputs (validated by pytest suite).
- All three priority rank scenarios are exercised (high-priority ready story, blocked story, low-signal story).
- Priority rank is never influenced by `story_points`; pytest asserts identical rank output with and without `story_points` populated.
- When no historical outcomes exist, `uncertainty_note` explicitly states "no historical outcomes available" for each affected decision.
- `PATCH /api/recommendations/{id}/mode-approve` requires a non-empty `approved_by`; sets `mode_approval_status: "approved"`, records `mode_approved_by` and `mode_approved_at`.
- `PATCH /api/recommendations/{id}/mode-override` requires non-empty `approved_by` and `override_reason`; sets `mode_approval_status: "overridden"`; returns 422 if `override_reason` is missing or empty.
- Downstream endpoints (`POST /api/bob-sessions`, `POST /api/outcomes`) return 409 Conflict when `mode_approval_status` is `"pending"`.
- Status: `[ ] pending`

### Milestone 4 — Bob session link and evidence capture
**Acceptance criteria:**
- `POST /api/bob-sessions` stores a session with summary, files, and optional commit SHA.
- When a commit SHA and `PIE_REPO_PATH` are set, the backend runs `git show --stat` and stores the diff summary.
- `GET /api/bob-sessions/{story_id}` returns the session.
- Status: `[ ] pending`

### Milestone 5 — Outcome recording and comparison
**Acceptance criteria:**
- `POST /api/outcomes` stores test result, build result, review notes, AC met flag, and optional `developer_id` (recorded as who actually did the work, without requiring a prior dev-match recommendation).
- `POST /api/comparisons` produces `mode_verdict` + `mode_explanation`. `dev_match_verdict` and `dev_match_explanation` columns exist in the model but are not populated in MVP (developer match is deferred).
- `GET /api/comparisons/{story_id}` returns the comparison.
- Status: `[ ] pending`

### Milestone 6 — React frontend
**Acceptance criteria:**
- Four screens exist and navigate in wizard order: Ticket Prioritization → Execution Mode → Link Bob Work → Outcome & Comparison.
- **Ticket Prioritization screen:** Shows a ranked list of open stories with priority, readiness, and blocker indicators. Selecting a story advances the wizard. Sample-data banner is displayed.
- **Execution Mode screen:** Renders mode badge, rationale, evidence list (with verified/unverified labels), risks, counterevidence, uncertainty note, and `ApprovalGate` component. Wizard does not advance until approval is given.
- **Link Bob Work screen:** Form submits and confirms.
- **Outcome & Comparison screen:** Shows mode verdict and explanation. `developer_id` field is a free-text input (no profile matching). Note that Developer Match screen is deferred.
- `SampleDataBanner` component is reused wherever `source === "sample"`.
- App runs via `npm run dev` and connects to the local backend.
- Status: `[ ] pending`

### Milestone 7 — Smoke test and demo readiness
**Acceptance criteria:**
- `scripts/smoke_test.sh` runs end-to-end without credentials and exits 0, exercising: sample story import (with visible `source_warning` in output), priority + execution-mode recommendation, the approval gate for execution mode (curl PATCH approve), the override failure path (missing `override_reason` → assert 422), Bob session link, outcome recording, and comparison generation.
- `BOB_USAGE.md` has at least one complete entry reflecting real implemented work.
- `context.md` reflects the final implementation state.
- Demo walkthrough (manual) matches the definition of done below.
- Status: `[ ] pending`

### Milestone 8 — Developer match (DEFERRED — future phase)
**Acceptance criteria (to be refined when scheduled):**
- `POST /api/developer-profiles/bootstrap-from-jira/{accountId}` — scans resolved Jira tickets, fetches merged PR links via dev-status API, extracts author/reviewer/file-path candidates, returns for human review. Does not write to profile until confirmed.
- `POST /api/developer-profiles/{id}/confirm-evidence` — writes confirmed candidates to the profile.
- `POST /api/recommendations` generates developer-match output alongside priority + mode.
- `PATCH /api/recommendations/{id}/dev-match-approve` and `.../dev-match-override` implement the independent approval gate.
- Developer Match wizard screen added.
- Outcome & Comparison screen extended with dev-match verdict.
- Status: `[ ] deferred`

---

## Definition of Done — First End-to-End Demo

1. User opens the app; Ticket Prioritization screen shows a ranked list of open stories (sample, labeled as such). Priority rationale, readiness signals, and blockers are visible per story.
2. User selects a story from the ranked list — this is a human choice; no gate, no approval required. The system records the selection and generates priority + execution-mode recommendations.
3. **Execution Mode screen:** Mode, evidence (with verified/unverified labels), risks, counterevidence, and uncertainty note are displayed. The `ApprovalGate` widget is shown. Approving or overriding the execution mode is a separate, explicit tech-lead action — distinct from selecting the ticket. Wizard advances only after the mode approval is recorded.
4. User notes the recommendation is saved with approval status before any work begins.
5. User enters a Bob session summary, lists files changed in PIE, and optionally provides a commit SHA.
6. Backend fetches the git diff summary (if SHA provided) and stores it.
7. User enters the actual test/build result, whether AC were met, and which developer did the work (free text — no profile matching in this phase).
8. App displays the comparison: original execution mode recommendation vs actual outcome (mode verdict + explanation).
9. User navigates back — all records persist across backend restarts (file-backed SQLite).
10. Demo clearly distinguishes what is implemented from what is deferred (Developer Match screen, developer skill verification, GitHub bootstrap) and what is not yet automated (Bob hook, live Jira if no credentials).

---

## Guardrails — What the System Must Never Do

These are non-negotiable constraints enforced at the service layer, not just at the UI layer:

1. **Never invent evidence.** Every item in `evidence[]` or `priority_evidence[]` must trace to a real record in the DB, a real Jira response field, or a real git/test output. If evidence is absent, say so. Distinguish observed facts (`verified: true`), unverified signals (`verified: false`), and inferences — all three are surfaced to the user, never collapsed into a single confident claim.
2. **Never equate missing experience with inability.** (Applies when Developer Match is built.) If a developer has no verified history with a domain in this system, the output is "no verified evidence of [domain] work in this system" — not "not suitable for this work".
3. **Never rank developers by AI activity.** (Applies when Developer Match is built.) Bob session count, token usage, or any AI-engagement metric must not influence `dev_match` scoring.
4. **Never auto-assign work.** `mode_approval_status` is always `"pending"` on creation. Downstream steps (`POST /api/bob-sessions`, `POST /api/outcomes`) return 409 Conflict while `mode_approval_status` remains `"pending"`. Work is treated as assigned only after a tech lead explicitly sets it to `"approved"` or `"overridden"`.
5. **Never silently substitute sample data.** Sample data is always labeled `source: "sample"` in the DB and displayed with a `[SAMPLE DATA]` banner in the UI. A failed or unconfigured Jira call always returns `source_status` and `source_warning` — never a silent sample-data fallback.
6. **Never claim stretch success prematurely.** (Applies when Developer Match is built.) `dev_match_verdict: "stretch_succeeded"` is only set when `Outcome.ac_met = true` and `Outcome.developer_id` matches the stretch-assigned developer.
7. **Never use story points for recommendations.** `story_points` is imported metadata only. It must not influence `priority_rank`, `mode`, or any recommendation output. The recommendation engine must produce identical output regardless of whether `story_points` is populated.
8. **Never allow an override without a reason.** `PATCH /api/recommendations/{id}/mode-override` with a missing or empty `override_reason` must be rejected at the API layer (422). The `mode_override_reason`, `mode_approved_by`, and `mode_approved_at` must all be non-null after any override.

---

## Single Best First Task

**Milestone 1 — Scaffold and documentation baseline.**

It is dependency-free, takes one focused Bob session, produces the structure every subsequent task depends on, and immediately generates a real `BOB_USAGE.md` entry. All later milestones reference paths and module names established here. The `sample_data/` directory and `DeveloperProfile` model introduced in Milestone 2 are named here so all subsequent Bob sessions share consistent naming.
