# Bob Intelligence — MVP Plan

## Top-Level Overview

**Goal:** Build a thin, demonstrable vertical slice that:
1. **Prioritizes** which open Jira ticket the team should work on next, based on priority, blockers, readiness, risk, and available context.
2. **Recommends an execution mode** — Bob-led, Collaborative (human + Bob), or Human-led — backed by *historical evidence* (semantically similar resolved PIE Jira tickets and their associated PRs) and current-code analysis, not just story metadata.
3. ~~**Suggests a developer match**~~ — **DEFERRED to a future phase.**

Both active recommendations are evidence-backed with explicit rationale, risk, missing evidence, and uncertainty. A tech lead must approve or override the execution-mode recommendation before work begins. No evidence is invented and no developer is ranked by AI activity.

**Scope:** Single-user, single-story demo. No auth, no multi-tenant, no org analytics.

**Approach:** Python + FastAPI backend with file-backed SQLite (via SQLAlchemy, `bob_intelligence.db`), React + TypeScript + Vite frontend, REST API. Recommendation logic is a rule engine enriched by historical Jira + PR evidence behind a service interface. Jira calls use the REST v3 API. When Jira credentials are absent or a Jira request fails, the response includes an explicit `source_status` warning and the caller must display a visible error; sample data is never silently substituted.

**Runtime (confirmed):**
- Python 3.14.0b4 — pre-release; use only stable stdlib and dependency features.
- Node v26.9.0 / npm 11.19.1 — current release, fully supported by Vite 5 and React 19.

**Frontend navigation:** Wizard-style (linear, step-by-step) — Ticket Prioritization → Execution Mode (with historical evidence panel) → Link Bob Work → Outcome & Comparison.

**Out of scope for current MVP:** developer match recommendations, developer ranking by any signal, skill verification, team matching, GitHub/Jira PR bootstrap, story-point estimation, forecasting dashboards, microservices, background workers, automated Bob session telemetry.

**Deferred to a future phase:** Decision 3 (Developer Match) — design retained in "Three Decisions" section below.

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
│   │   ├── recommendations.py   # /api/recommendations endpoints (mode + priority)
│   │   ├── bob_sessions.py      # /api/bob-sessions endpoints
│   │   └── outcomes.py          # /api/outcomes endpoints
│   ├── services/
│   │   ├── jira_service.py      # Jira REST v3 client + sample-data fallback
│   │   ├── recommendation_service.py  # Rule engine: priority, mode (enriched with historical + LLM evidence)
│   │   ├── historical_evidence_service.py  # NEW M4a: TF-IDF similarity + PR evidence + outcome/session evidence
│   │   ├── llm_service.py       # NEW M4b: LLM provider abstraction (watsonx/openai); analyze_pr() interface
│   │   ├── dev_profile_service.py     # Developer profile loader + evidence aggregator
│   │   └── evidence_service.py  # Git diff / test result capture helpers
│   ├── sample_data/
│   │   ├── stories.json         # [SAMPLE DATA] labeled stories
│   │   ├── resolved_tickets.json  # NEW M4a: [SAMPLE DATA] resolved PIE tickets with PR links
│   │   └── developer_profiles.json  # [SAMPLE DATA] labeled developer profiles
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── TicketPrioritization.tsx    # step 1 of wizard
│   │   │   ├── RecommendationView.tsx      # execution mode + historical evidence panel (step 2)
│   │   │   ├── LinkBobWork.tsx             # step 3
│   │   │   └── OutcomeComparison.tsx       # step 4 — AC-level comparison
│   │   ├── components/
│   │   │   ├── SampleDataBanner.tsx        # Reusable [SAMPLE DATA] banner
│   │   │   ├── EvidenceList.tsx            # Evidence + uncertainty display
│   │   │   ├── HistoricalEvidencePanel.tsx  # NEW M6: shows similar tickets + PR links
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
     │                                                └─► sample_data/stories.json
     ├── /api/recommendations      ──► recommendation_service
     │                                   ├── priority_engine              (ticket prioritization)
     │                                   ├── historical_evidence_service  (NEW M4a — runs first)
     │                                   │     ├── semantic_search        (resolved ticket similarity)
     │                                   │     ├── pr_evidence            (GitHub API: diff, files, merge, reverts)
     │                                   │     ├── outcome_evidence       (Outcome + BobSession records for similar stories)
     │                                   │     └── llm_analysis           (NEW M4b — LLM reads PR diff + story context)
     │                                   │           ├── similarity_judgment   (is this PR relevant to the ticket?)
     │                                   │           ├── code_quality_analysis (complexity, tests, risk patterns)
     │                                   │           └── intervention_analysis (BobSession.human_interventions signal)
     │                                   └── mode_engine                  (Bob/Collab/Human — consumes all evidence)
     ├── /api/bob-sessions         ──► SQLite (draft + confirmed sessions)
     │                                   ├── Bob stop hook  (auto-creates draft on task end)
     │                                   └── PATCH .../confirm  (user reviews + confirms draft)
     └── /api/outcomes             ──► evidence_service ──► Git CLI / test output files
                                                      └─► SQLite
```

---

## Core Entities

```
Story
  id                 TEXT PK
  jira_key           TEXT          -- e.g. PIE-42
  title              TEXT
  description        TEXT
  acceptance_criteria TEXT
  story_points       INT nullable  -- imported metadata only; MUST NOT influence recommendations
  labels             JSON
  priority           TEXT nullable
  status             TEXT nullable
  assignee           TEXT nullable
  blockers           JSON
  linked_prs         JSON
  source             TEXT          -- "jira" | "sample"
  created_at         DATETIME

Recommendation
  id                 TEXT PK
  story_id           TEXT FK → Story
  -- Ticket prioritization (advisory)
  priority_rank      INT nullable
  priority_rationale TEXT nullable
  priority_evidence  JSON
  -- Execution mode (now enriched with historical evidence)
  mode               TEXT          -- "bob_led" | "collaborative" | "human_led"
  mode_rationale     TEXT
  mode_evidence      JSON          -- includes historical_ticket and pr_evidence items
  mode_risks         JSON
  mode_counterevidence JSON
  mode_approval_status TEXT        -- "pending" | "approved" | "overridden"
  mode_approved_by   TEXT nullable
  mode_approved_at   DATETIME nullable
  mode_override_reason TEXT nullable
  -- Historical evidence (NEW — populated by historical_evidence_service in M4a)
  similar_tickets    JSON          -- list of {jira_key, title, similarity_score, resolution, mode_used}
  supporting_prs     JSON          -- list of {url, title, merged, files_changed, summary}
  code_analysis_notes TEXT nullable -- current-code inspection summary
  evidence_confidence TEXT nullable -- "high"|"medium"|"low"|"none" based on historical signal strength
  -- Developer match fields (DEFERRED — columns preserved)
  suggested_developer TEXT nullable
  dev_match_rationale TEXT nullable
  dev_match_evidence  JSON
  dev_match_risks     JSON
  is_stretch_assignment BOOLEAN
  stretch_support_plan TEXT nullable
  dev_match_approval_status TEXT
  dev_match_approved_by TEXT nullable
  dev_match_approved_at DATETIME nullable
  dev_match_override_reason TEXT nullable
  -- Shared
  uncertainty_note   TEXT
  created_at         DATETIME
  status             TEXT          -- "pending" | "superseded"

ResolvedTicket (NEW — Milestone 4a)
  id                 TEXT PK
  jira_key           TEXT          -- e.g. PIE-30
  title              TEXT
  description        TEXT
  resolution         TEXT          -- "Done" | "Won't Fix" | etc.
  labels             JSON
  linked_prs         JSON          -- PR URLs discovered from Jira remotelinks or dev-status
  files_changed      JSON          -- union of files across all linked PRs
  mode_used          TEXT nullable -- "bob_led"|"collaborative"|"human_led" if recorded
  ac_met             BOOLEAN nullable
  source             TEXT          -- "jira" | "sample"
  created_at         DATETIME

PREvidence (NEW — Milestone 4b)
  id                 TEXT PK
  resolved_ticket_id TEXT FK → ResolvedTicket nullable
  story_id           TEXT FK → Story nullable  -- links to current story if PR is directly referenced
  url                TEXT          -- full PR URL
  title              TEXT
  merged             BOOLEAN
  base_branch        TEXT nullable
  head_branch        TEXT nullable
  files_changed      JSON          -- list of file paths
  diff_summary       TEXT nullable -- short prose summary of what changed
  test_files_present BOOLEAN nullable -- whether test files appear in the diff
  was_reverted       BOOLEAN nullable -- whether a follow-up PR reverted this
  source             TEXT          -- "jira_remotelink" | "github_api" | "sample"
  created_at         DATETIME

BobSession
  id                 TEXT PK
  story_id           TEXT FK → Story
  status             TEXT          -- "draft" | "confirmed"
  summary            TEXT nullable -- null on draft; set by user on confirm (pre-filled from auto_generated_summary)
  auto_generated_summary TEXT nullable -- generated when hook fires; never presented as final without user review
  files_changed      JSON          -- populated by hook or manually supplied
  pie_commit_sha     TEXT nullable
  diff_summary       TEXT nullable -- populated by git show --stat when pie_commit_sha is set
  test_result        TEXT nullable -- "pass"|"fail"|"skipped"
  human_interventions JSON          -- list of free-text intervention notes added during confirm
  hook_triggered_at  DATETIME nullable -- when the Bob stop hook fired (null if created manually)
  created_at         DATETIME

Outcome
  id                 TEXT PK
  story_id           TEXT FK → Story
  bob_session_id     TEXT FK → BobSession nullable
  developer_id       TEXT FK → DeveloperProfile nullable
  test_result        TEXT nullable -- "pass" | "fail" | "skipped"
  build_result       TEXT nullable -- "pass" | "fail"
  review_notes       TEXT nullable
  ac_met             TEXT nullable  -- CHANGED: "successful"|"partial"|"failed"|"unverified" (was boolean)
  ac_detail          JSON           -- NEW: list of {criterion, met: bool, notes} per AC item
  diff_summary       TEXT nullable
  created_at         DATETIME

Comparison
  id                 TEXT PK
  recommendation_id  TEXT FK → Recommendation
  outcome_id         TEXT FK → Outcome
  mode_verdict       TEXT nullable  -- "confirmed" | "exceeded" | "diverged"
  mode_explanation   TEXT nullable
  ac_verdict         TEXT nullable  -- NEW: "successful"|"partial"|"failed"|"unverified"
  ac_explanation     TEXT nullable  -- NEW: per-AC summary
  dev_match_verdict  TEXT nullable  -- DEFERRED
  dev_match_explanation TEXT nullable
  created_at         DATETIME
```

---

## REST Endpoints (Minimum Viable)

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | /api/health | Liveness check | ✅ M1 |
| GET | /api/stories | List imported stories | ✅ M2 |
| POST | /api/stories/import | Import story from Jira or sample data | ✅ M2 |
| GET | /api/stories/{id} | Get single story | ✅ M2 |
| GET | /api/developer-profiles | List developer profiles | ✅ M2 |
| POST | /api/developer-profiles/import-sample | Import sample developer profiles | ✅ M2 |
| POST | /api/recommendations | Generate priority + execution-mode + historical evidence | ✅ M3 (mode only) → enriched in M4a |
| GET | /api/recommendations/{id} | Get recommendation | ✅ M3 |
| PATCH | /api/recommendations/{id}/mode-approve | Tech lead approves execution mode | ✅ M3 |
| PATCH | /api/recommendations/{id}/mode-override | Tech lead overrides; requires override_reason | ✅ M3 |
| POST | /api/resolved-tickets/import | Import resolved tickets from Jira or sample data | NEW M4a |
| GET | /api/resolved-tickets | List resolved tickets | NEW M4a |
| POST | /api/bob-sessions | Create Bob session link (approval-gated) | Stub M3 → full M4c |
| GET | /api/bob-sessions/{story_id} | Get sessions for a story | Stub M3 → full M4c |
| POST | /api/outcomes | Record outcome for a story (approval-gated) | Stub M3 → full M5 |
| GET | /api/outcomes/{story_id} | Get outcome for a story | Stub M3 → full M5 |
| POST | /api/comparisons | Generate mode + AC comparison | NEW M5 |
| GET | /api/comparisons/{story_id} | Get comparison for a story | Stub M3 → full M5 |
| POST | /api/developer-profiles | Create or upsert a developer profile | DEFERRED |
| POST | /api/recommendations/{id}/dev-match-approve | Developer match approval gate | DEFERRED |
| POST | /api/recommendations/{id}/dev-match-override | Developer match override | DEFERRED |

---

## Frontend Screens

| Screen | Route | Purpose | Status |
|--------|-------|---------|--------|
| Ticket Prioritization | `/` | Ranked open stories with priority, readiness, blocker indicators | M6 |
| Execution Mode | `/stories/:id/recommendation` | Mode badge, rationale, evidence (including historical evidence panel with similar tickets + clickable PR links), risks, counterevidence, uncertainty, approval gate | M6 |
| Link Bob Work | `/stories/:id/bob-session` | Submit Bob session summary, files, commit SHA, human interventions | M6 |
| Outcome & Comparison | `/stories/:id/outcome` | Per-AC results, mode verdict, evidence traceability links | M6 |
| Developer Match | `/stories/:id/developer` | **DEFERRED** | M8 |

---

## Three Decisions — Design Detail

### Decision 1: Ticket Prioritization

**Purpose:** Surface the single best next ticket from a list of open stories.

**Input signals (unchanged from M3):**
- Jira `priority` field (Highest → Lowest)
- Presence and count of blocking issues (`blockers[]`)
- Story `status` (e.g. "Ready for Dev" ranks above "Backlog")
- Acceptance criteria completeness
- Label keywords indicating risk or urgency
- Dependency chains inferred from linked issues
- Number of open unknowns detected in description text

**Explicitly excluded:**
- `story_points` — never influences any recommendation

**Constraint:** Priority rank is advisory. The tech lead explicitly selects a story. No approval gate for prioritization.

---

### Decision 2: Execution Mode (enriched in M4a/M4b)

**Purpose:** Recommend whether the selected ticket should be Bob-led, Collaborative, or Human-led.

**Input signals (story-structure only — label keywords removed):**
- Description length and structure
- Presence and quality of acceptance criteria
- Number of open unknowns detected in description text
- `blockers[]`
- `linked_prs`
- Historical `Comparison` records in DB

> **Note:** Label-based scoring (`_BOB_LED_LABELS`, `_HUMAN_LED_LABELS`, `_COLLAB_LABELS`) was removed. Label taxonomies are org-specific and unreliable across teams. Mode is now driven entirely by story-structure signals and historical evidence.

**NEW input signals (M4a and later):**
- `similar_tickets[]` — semantically similar resolved PIE tickets: their resolution, whether AC was met, and which mode was recorded. When ≥1 resolved ticket with `ac_met = True` and mode recorded exists, the mode engine uses it as a positive signal.
- `supporting_prs[]` — PRs discovered via similar tickets: merge status, file overlap with current story, presence of test files, and reverts. A PR touching the same files as the new story is a positive signal for Bob-led; a revert is a risk signal.
- `llm_analysis` — (NEW M4b) LLM-generated analysis of each PR diff against the new story. Provides: relevance judgment, prose diff summary, code quality signals, and risk flags. Replaces pattern-matching for `diff_summary` and `code_analysis_notes`. Falls back to pattern-matching when `LLM_API_KEY` is absent.
- `outcome_evidence[]` — (NEW M4b) `Outcome` records for similar stories: `ac_met`, `ac_detail`, `test_result`, `build_result`. Surfaces whether similar work actually succeeded per acceptance criterion.
- `bob_session_evidence[]` — (NEW M4b) `BobSession.human_interventions` records for similar stories. A high count of human interventions on similar past work is a direct signal that Bob needed help — reduces Bob-led confidence.
- `code_analysis_notes` — prose summary from LLM analysis (replaces file-count inspection). Null when LLM unavailable and `PIE_REPO_PATH` not set.
- `evidence_confidence` — "high" when ≥3 similar tickets with recorded outcomes exist; "medium" 1–2; "low" when tickets exist but no outcomes; "none" when no similar tickets found. Always surfaced in `uncertainty_note`.

**Rule categories (extended):**
- **Complexity signals** → favor Human-led (description unknowns, missing AC, blockers)
- **Routine/pattern signals** → favor Bob-led (detailed AC, well-structured description, linked PRs)
- **~~Risk signals → flag security/infra labels~~** → **removed** (label taxonomy is org-specific)
- **Historical success pattern** → if similar resolved tickets exist with `ac_met = True` and mode recorded, boost mode score toward that recorded mode
- **Historical failure / revert pattern** → if similar resolved PRs have `was_reverted = True`, add risk item and reduce Bob-led score
- **LLM code quality signal** → if LLM flags PR code as complex, risky, or poorly tested, add risk item and reduce Bob-led score; if LLM confirms clean patterns and good tests, boost Bob-led score
- **Intervention pattern** → if `BobSession.human_interventions` count is high across similar stories, reduce Bob-led score; near-zero interventions boost Bob-led score
- **Outcome evidence** → `Outcome.ac_met = "successful"` on similar stories boosts Bob-led; `"partial"` or `"failed"` adds risk items and reduces score
- **Evidence availability** → if no historical outcomes or tickets exist, `uncertainty_note` is set and confidence is reduced (unchanged behavior preserved)

**Trust ladder — mode is not permanent:**
The mode recommendation for a ticket type evolves as evidence accumulates across the system's lifetime:
- `human_led` — no history or prior failures; human drives, Bob observes
- `collaborative` — one or more similar tickets succeeded; Bob assists, human reviews
- `bob_led` — multiple verified successes, low intervention count, clean PR history; Bob owns

A ticket type can regress from `bob_led` → `collaborative` if a `was_reverted = True` PR or a run of `ac_met = "failed"` outcomes appears for similar work. The system never permanently fixes a mode; every new recommendation re-evaluates all available evidence.

**Output:** all existing M3 fields plus `similar_tickets[]`, `supporting_prs[]`, `code_analysis_notes`, `evidence_confidence`, `llm_pr_analysis[]`

---

### Decision 3: Developer Match — DEFERRED

> **Status: deferred to a future phase.** All model columns preserved. Design retained below for when this phase is resumed.

---

## Explainable Recommendation Approach

The recommendation engine scores a story against a fixed set of transparent rules. No probabilities are invented. Historical evidence items are clearly labeled with their source (Jira ticket key, PR URL, DB record).

The `RecommendationService.generate(story, developer_profiles) → Recommendation` interface is kept clean so an LLM or watsonx call can replace or augment any sub-engine later without changing the API layer.

**Shared output envelope for all decisions:**
```
rationale:         prose explanation
evidence[]:        list of {source, description, verified: bool}
risks[]:           list of {description, severity: "low"|"medium"|"high"}
counterevidence[]: list of {description}
uncertainty_note:  explicit prose about what evidence is absent
similar_tickets[]: list of {jira_key, title, similarity_score, resolution, mode_used, ac_met}
supporting_prs[]:  list of {url, title, merged, files_changed, test_files_present, was_reverted, diff_summary}
code_analysis_notes: prose or null
evidence_confidence: "high"|"medium"|"low"|"none"
```

---

## Jira Integration

**Approach:** Wire the live Jira REST v3 API. When credentials are absent or a Jira request fails, the backend returns an explicit `source_status` field along with a human-readable `source_warning`. Sample data is always labeled `source: "sample"` and displayed with a `[SAMPLE DATA]` banner.

**NEW for M4a:** Resolved tickets are fetched via `GET /rest/api/3/search?jql=project=PIE+AND+status=Done&fields=summary,description,labels,status,issuelinks,remoteLinks` (or equivalent). PR links are discovered via `GET /rest/api/3/issue/{key}/remotelink` (Jira remotelinks). When credentials are absent, the sample resolved ticket dataset is used with a visible warning.

---

## Semantic Similarity Approach (M4a)

**Approach (no external ML dependency):** TF-IDF cosine similarity between the new story's `title + description + labels` and each resolved ticket's `title + description + labels`. This is deterministic, requires no external API key, and runs in-process.

**Threshold:** A resolved ticket is considered "similar" when cosine similarity ≥ 0.25. The top 5 similar tickets are returned.

**Why not embeddings in MVP:** Embedding APIs (OpenAI, watsonx) require credentials and add network latency. TF-IDF is sufficient for demonstrating the concept and can be upgraded to embeddings in a later phase. The `historical_evidence_service` interface is written so the similarity backend can be swapped without changing the recommendation service.

**Sample data:** `sample_data/resolved_tickets.json` provides ≥5 resolved PIE tickets with labels, description, linked PRs, and `mode_used` + `ac_met` pre-populated so the pipeline demonstrates end-to-end without live Jira credentials.

---

## PR Evidence Discovery (M4b)

**Approach:**
1. For each similar resolved ticket, collect `linked_prs[]` (PR URLs).
2. Additionally scan current story's own `linked_prs[]`.
3. For each unique PR URL, call the GitHub REST API (`GET /repos/{owner}/{repo}/pulls/{number}`) to fetch: title, merged status, base/head branch, file list (`/files`), and check for a subsequent revert PR (by searching commits or PR titles).
4. When `GITHUB_TOKEN` is absent, PR metadata is limited to what is available in Jira remotelinks. Missing GitHub data is recorded as `source_warning` — never silently omitted.
5. `test_files_present` is set to `True` when any file in the PR diff matches `test_*.py`, `*_test.py`, `*.spec.*`, or `tests/`. When LLM is available, LLM judgment supersedes pattern-matching.
6. `was_reverted` is set to `True` when a PR title or body contains `revert` (case-insensitive) and references the original PR number.
7. **NEW:** After GitHub metadata is fetched, `llm_service.analyze_pr(story, pr_diff)` is called. The LLM receives the full PR diff and the new story text and returns a structured analysis (see LLM Analysis section). Result is stored as `PREvidence.diff_summary` and `PREvidence.code_analysis_notes`. When `LLM_API_KEY` is absent or the call fails, falls back to pattern-matching and records `source_warning`.

**Sample data:** Pre-populated `PREvidence` records in `resolved_tickets.json` so the pipeline works without GitHub credentials.

---

## LLM Analysis (M4b — NEW)

**Purpose:** Replace shallow pattern-matching with LLM-generated analysis that can judge PR relevance, code quality, and risk signals in natural language — providing richer evidence for the mode engine.

**What the LLM receives (prompt context):**
- New story: `title`, `description`, `acceptance_criteria`, `labels`
- Resolved ticket: `title`, `description`, `mode_used`, `ac_met`
- PR metadata: `title`, `files_changed`, `merged`, `was_reverted`
- PR diff: full code diff from GitHub API
- Outcome records for the resolved ticket: `ac_met`, `ac_detail`, `test_result`
- BobSession records for the resolved ticket: `human_interventions[]`, `summary`

**What the LLM returns (structured JSON):**
```json
{
  "relevant": true,
  "relevance_reason": "PR addresses the same auth token refresh pattern as the new story",
  "diff_summary": "Refactored token refresh to use sliding window. Added 3 unit tests. No DB migration.",
  "has_tests": true,
  "complexity": "low",
  "risk_flags": [],
  "intervention_signal": "low",
  "mode_signal": "bob_led",
  "mode_rationale": "Clean pattern, well-tested, prior attempt succeeded with zero interventions"
}
```

**How the LLM output feeds the mode engine:**
- `mode_signal` from LLM becomes an evidence item in `mode_evidence[]` with `source: "llm_pr_analysis"`
- `risk_flags[]` from LLM are added to `mode_risks[]`
- `intervention_signal = "high"` reduces the Bob-led mode score
- `has_tests = false` adds a risk item and reduces Bob-led score
- `relevant = false` means the PR is excluded from evidence (not surfaced as a supporting PR)

**Fallback when LLM is unavailable:**
- `LLM_API_KEY` absent or call fails → pattern-matching used for `test_files_present` and `was_reverted`
- `code_analysis_notes` is null
- `source_warning` records "LLM analysis unavailable — LLM_API_KEY not configured" or the error
- Mode engine continues with reduced evidence; `uncertainty_note` states LLM was unavailable

**LLM provider:** Configurable via `LLM_PROVIDER` env var. Supported values: `watsonx`, `openai`. When absent, LLM analysis is skipped entirely. The `llm_service.py` interface abstracts provider differences so the recommendation service never calls a provider directly.

---

## Outcome and BobSession Evidence (M4b — NEW)

**Purpose:** Wire `Outcome` and `BobSession` records for similar stories directly into the mode recommendation. This is the most honest evidence source — it reflects what actually happened when Bob attempted similar work.

**What is pulled per similar resolved ticket:**
- `Outcome` records linked to the resolved ticket's story: `ac_met`, `ac_detail` (per-criterion), `test_result`, `build_result`
- `BobSession` records linked to the resolved ticket's story: `human_interventions[]`, `summary`, `files_changed`

**How it feeds the mode engine:**
- `Outcome.ac_met = "successful"` → strong positive signal; boost Bob-led score
- `Outcome.ac_met = "partial"` → risk item: "similar story had partial outcome"; moderate Bob-led reduction
- `Outcome.ac_met = "failed"` → risk item: "similar story failed"; strong Bob-led reduction
- `BobSession.human_interventions` count = 0 across all similar sessions → boost Bob-led score
- `BobSession.human_interventions` count 1–2 → collaborative signal
- `BobSession.human_interventions` count ≥ 3 → human-led signal; add risk item

**When no Outcome or BobSession records exist for similar tickets:** `uncertainty_note` states "no outcome or session records found for similar stories — confidence based on ticket metadata and PR analysis only."

---

## Current-Code Analysis (M4b — revised)

**Approach:** `code_analysis_notes` is now populated by the LLM rather than a file-count inspection. When the LLM is available, it produces a prose summary of what the codebase looked like in similar PRs (patterns, test coverage, structural familiarity). When the LLM is unavailable and `PIE_REPO_PATH` is set, a shallow file inspection runs as fallback:
- Count Python/JS files in directories most frequently modified by similar PRs.
- Check whether test files exist alongside source files in those directories.
- Record file-naming patterns (e.g. `service.py`, `router.py`, `test_*.py`) that indicate structural familiarity.

When neither the LLM nor `PIE_REPO_PATH` is available, `code_analysis_notes` is `null` and `uncertainty_note` states "code analysis unavailable — LLM_API_KEY and PIE_REPO_PATH not configured."

---

## Self-Learning Mechanism (M5b)

**What self-learning means here:** When a `Comparison` record is created with `ac_verdict = "successful"` and the `Recommendation.mode` matches the outcome, that completed story becomes a new `ResolvedTicket` record (if not already one from Jira). On the next call to `POST /api/recommendations` for a similar story, this record enters the similarity search and its mode + ac_met status acts as a positive signal.

**Why this is real learning (not just storage):** The feedback loop is closed: the similarity search result set grows with each verified outcome, changing future recommendation scores. The `evidence_confidence` field changes from "none" → "low" → "medium" → "high" as more verified outcomes accumulate, and this change is visible to the caller.

**Trust ladder progression:** The mode recommendation for a ticket type is not fixed. It evolves across the system's lifetime:
- A ticket type first seen with no history starts at `human_led` (or `collaborative` if metadata signals are strong).
- After one verified successful outcome, the next similar ticket has `evidence_confidence: "low"` and the mode score shifts toward the recorded `mode_used`.
- After ≥3 verified successful outcomes with low intervention counts, `evidence_confidence` reaches `"high"` and the mode score strongly favors `bob_led` — provided no reversions or failures appear.
- A `was_reverted = True` PR or `ac_met = "failed"` outcome resets confidence downward and adds risk items, which can pull the mode back from `bob_led` → `collaborative`.

**Hard constraints:**
- Only outcomes with `ac_verdict = "successful"` and a non-null `recommendation_id` are promoted to the resolved ticket pool.
- Partial, failed, and unverified outcomes are stored and surfaced as risk signals ("similar story had partial outcome") but do not become positive signals.
- `uncertainty_note` always states the count of verified outcomes used. "0 verified outcomes" is never presented as a positive signal.
- The LLM never directly sets the mode. It produces evidence items (`mode_signal`, `risk_flags`) that feed the mode engine's score. The rule engine makes the final call.

---

## Bob Execution Session (M4c)

**Two creation paths — same `BobSession` record, different entry points:**

**Path A — Bob hook (automatic):**
When a Bob task ends, a `stop` lifecycle hook fires a `POST /api/bob-sessions` with the story ID, list of files changed during the session, and an auto-generated summary of what Bob did. The record is created with `status = "draft"`. The auto-generated summary is stored in `auto_generated_summary` and pre-fills the `summary` field in the UI for the user to review. `hook_triggered_at` is set to the hook fire time.

**Path B — Manual entry:**
The user can also `POST /api/bob-sessions` directly (no hook) with any fields they supply. The record is created with `status = "draft"` immediately ready to confirm.

**Confirmation step (both paths):**
The user reviews the draft in the UI — editing the summary, adding human intervention notes, and optionally providing a commit SHA — then calls `PATCH /api/bob-sessions/{id}/confirm`. This sets `status = "confirmed"` and, if `pie_commit_sha` is present and `PIE_REPO_PATH` is set, triggers `git show --stat` to populate `diff_summary`. Only confirmed sessions are linked to outcomes.

**Hard constraints:**
- `auto_generated_summary` is never surfaced as the final `summary` without explicit user confirmation. The UI must show a visible "draft — review required" state for unconfirmed sessions.
- The hook may be absent or fail (Bob lifecycle hooks are best-effort). When no hook fires, the manual path is the fallback. `hook_triggered_at` being null is a normal state.
- `POST /api/outcomes` requires at least one confirmed `BobSession` for the story (or `bob_session_id` explicitly provided). If the session is still draft, outcomes return 409.

**What is recorded on a confirmed session:**
- `summary` — user-reviewed prose of what Bob attempted and accomplished
- `auto_generated_summary` — the original hook-generated text, preserved for audit
- `files_changed[]` — file paths (from hook or manually entered)
- `pie_commit_sha` — optional commit SHA
- `diff_summary` — populated by git on confirm when SHA is set
- `test_result` — pass / fail / skipped
- `human_interventions[]` — free-text list of manual interventions added during confirm
- `hook_triggered_at` — timestamp of hook fire, or null if manual

---

## Requirement-Level Outcome (M5a)

**Change from original plan:** `ac_met` is no longer a single boolean. It is:
- `ac_met: "successful" | "partial" | "failed" | "unverified"` (text column, replaces BOOLEAN)
- `ac_detail: JSON` — list of `{criterion: str, met: bool, notes: str | null}` per AC item, populated when the user enters per-criterion results

This is a schema migration on the `Outcome` table. The existing boolean column is renamed and the type changed; any existing rows (none in production, tests start fresh) are unaffected.

---

## Testing Strategy

- **Backend:** `pytest` with `httpx.AsyncClient` against the FastAPI app. Tests use an isolated `bob_intelligence_test.db` created fresh at test session start and deleted on teardown.

  **Required test cases for new milestones (in addition to all M1-M3 tests):**

  *M4a — Historical ticket retrieval:*
  - Import sample resolved tickets; assert count returned matches sample data.
  - Call `POST /api/recommendations` for a story with high text overlap to a sample resolved ticket; assert `similar_tickets` is non-empty and contains the expected jira_key.
  - Call `POST /api/recommendations` for a story with no text overlap; assert `similar_tickets` is empty and `evidence_confidence = "none"`.
  - Assert `similar_tickets` items each contain `jira_key`, `title`, `similarity_score`, `resolution`.
  - Assert `supporting_prs` items (from sample data) each contain `url`, `merged`, `files_changed`.
  - Assert `evidence_confidence` is "low" with 1 similar ticket, "medium" with 2, "high" with ≥3.
  - Assert mode score is higher for a story whose similar tickets all have `mode_used = "bob_led"` and `ac_met = True` vs an equivalent story with no similar tickets.

  *M4b — PR evidence, LLM analysis, and outcome/session evidence:*
  - When `PIE_REPO_PATH` is not set and `LLM_API_KEY` is not set, `code_analysis_notes` is null and `uncertainty_note` mentions both.
  - `test_files_present` is True when PR file list contains `test_*.py` (pattern fallback when LLM absent).
  - `was_reverted` is True when a PR title contains "Revert" and references the original PR number.
  - When `LLM_API_KEY` is set, `PREvidence.diff_summary` is populated with LLM-generated prose (not raw diff).
  - LLM `relevant = false` causes the PR to be absent from `supporting_prs[]` in the recommendation response.
  - LLM `mode_signal = "bob_led"` adds a `source: "llm_pr_analysis"` evidence item to `mode_evidence[]`.
  - LLM `risk_flags` are present in `mode_risks[]`.
  - When `LLM_API_KEY` is absent, `source_warning` is present and `uncertainty_note` states LLM was unavailable.
  - When similar resolved tickets have linked `Outcome` records with `ac_met = "successful"`, a positive evidence item appears in `mode_evidence[]`.
  - When similar resolved tickets have linked `Outcome` records with `ac_met = "failed"`, a risk item appears in `mode_risks[]`.
  - When similar resolved tickets have linked `BobSession` records with `human_interventions` count ≥3, a risk item appears in `mode_risks[]`.
  - When similar resolved tickets have linked `BobSession` records with zero `human_interventions`, a positive evidence item appears in `mode_evidence[]`.
  - Mode score is lower for a story whose similar sessions had high intervention counts vs. one with zero.

  *M4c — Bob session:*
  - `POST /api/bob-sessions` with valid approved story creates a BobSession record with `status = "draft"`.
  - `POST /api/bob-sessions` with `auto_generated_summary` stores the hook-generated text; `summary` remains null until confirmed.
  - `PATCH /api/bob-sessions/{id}/confirm` sets `status = "confirmed"`, sets `summary` from body (pre-filled by auto_generated_summary), stores human_interventions.
  - `GET /api/bob-sessions/{story_id}` returns all sessions including draft ones.
  - `POST /api/bob-sessions` returns 409 when mode_approval_status is pending.
  - `POST /api/outcomes` returns 409 when no confirmed session exists for the story.
  - Session with `pie_commit_sha` and `PIE_REPO_PATH` set on confirm populates `diff_summary` (mocked git call).
  - Session without `pie_commit_sha` leaves `diff_summary` null.
  - `human_interventions` list is stored and returned correctly on the confirmed record.
  - `hook_triggered_at` is stored when provided; null when created manually.
  - A draft session does not block further `POST /api/bob-sessions` calls for the same story (multiple drafts allowed before confirm).

  *M5a — Requirement-level outcome:*
  - `POST /api/outcomes` with `ac_met = "partial"` and `ac_detail` stores both fields.
  - `POST /api/outcomes` with `ac_met = "successful"` creates a Comparison record.
  - `POST /api/outcomes` returns 409 when mode_approval_status is pending.
  - Each ac_detail item contains `criterion`, `met`, `notes`.
  - `GET /api/outcomes/{story_id}` returns ac_detail.

  *M5b — Comparison and self-learning:*
  - `POST /api/comparisons` produces `mode_verdict` and `ac_verdict`.
  - `mode_verdict = "confirmed"` when recorded mode matches recommendation mode and ac_met = "successful".
  - `mode_verdict = "diverged"` when actual mode differs from recommendation.
  - A successful outcome promotes the story to the resolved ticket pool (new ResolvedTicket created).
  - Next `POST /api/recommendations` for a similar story references the newly promoted resolved ticket in `similar_tickets`.
  - Failed and partial outcomes appear as risk signals, not positive signals.

  *M6 — UI (manual walkthrough; no automated frontend tests in MVP):*
  - HistoricalEvidencePanel renders similar ticket list with clickable PR links.
  - ApprovalGate blocks wizard progression until approved.

- **Integration smoke test:** Updated `scripts/smoke_test.sh` adds:
  - Import sample resolved tickets.
  - Assert `POST /api/recommendations` returns non-empty `similar_tickets` and valid `evidence_confidence`.
  - Full Bob session create and retrieve.
  - Full outcome create with `ac_met = "partial"` and `ac_detail`.
  - Comparison generate and retrieve.
  - Assert self-learning: a second recommendation after a successful outcome references the promoted resolved ticket.

---

## Implementation Milestones

### Milestone 1 — Scaffold and documentation baseline
**Status: `[x] complete`** — verified 2025-07-14. Health endpoint returns 200. Smoke test exits 0.

### Milestone 2 — Data layer and story import
**Status: `[x] complete`** — verified 2025-07-15. 33/33 tests passing. Smoke test exits 0.

### Milestone 3 — Recommendation engine (priority + execution mode)
**Status: `[x] complete`** — verified 2025-07-15. 75/75 tests passing (42 new + 33 M2). Smoke test 20/20.

**What M3 delivers:**
- `POST /api/recommendations` → `priority_rank`, `priority_rationale`, `priority_evidence[]`, `mode`, `mode_rationale`, `mode_evidence[]`, `mode_risks[]`, `mode_counterevidence[]`, `uncertainty_note`
- `PATCH .../mode-approve` and `PATCH .../mode-override` with 422 on missing override reason
- 409 Conflict gates on `POST /api/bob-sessions` and `POST /api/outcomes` while mode is pending
- Developer-match fields present in model, not populated
- `story_points` never read by any engine
- Bob session and outcome endpoints return 501 after gate passes

---

### Milestone 4a — Historical ticket retrieval and semantic similarity ← **NEXT INCOMPLETE MILESTONE**

**Intent:** Enrich the mode recommendation with semantically similar resolved PIE tickets, discovered via TF-IDF cosine similarity. This is the foundation for all subsequent historical-evidence features. Without it, PR evidence discovery (M4b) and self-learning (M5b) have no ticket corpus to work from.

**Acceptance criteria:**
- `ResolvedTicket` ORM model exists with all fields from Core Entities above.
- `POST /api/resolved-tickets/import` with `source=sample` creates resolved ticket records from `sample_data/resolved_tickets.json`. Records are labeled `source: "sample"` and import is idempotent (duplicates skipped by `jira_key`).
- `POST /api/resolved-tickets/import` with `source=jira` calls `GET /rest/api/3/search?jql=project=PIE AND status=Done` (or configured JQL), returns `source_status` and `source_warning`. When credentials absent, returns `source_status: "credentials_missing"`.
- `GET /api/resolved-tickets` returns all resolved tickets with `total`.
- `historical_evidence_service.find_similar(story, db)` returns up to 5 `ResolvedTicket` records with cosine similarity ≥ 0.25, ordered by score descending.
- `POST /api/recommendations` response now includes:
  - `similar_tickets[]` — list of `{jira_key, title, similarity_score, resolution, mode_used, ac_met}`
  - `supporting_prs[]` — union of `linked_prs` from similar tickets (populated from ResolvedTicket records; GitHub enrichment deferred to M4b)
  - `evidence_confidence` — "high" (≥3 similar with outcomes), "medium" (1–2), "low" (similar exist but no outcomes), "none" (no similar tickets)
  - `code_analysis_notes` — null in M4a (populated in M4b)
- Mode score is adjusted: +10 when ≥2 similar tickets have `mode_used = "bob_led"` and `ac_met = True`; -10 when ≥1 similar ticket has `was_reverted = True` (from PREvidence or resolved ticket metadata).
- When no similar tickets found, `uncertainty_note` includes "no similar resolved tickets found."
- `sample_data/resolved_tickets.json` contains ≥5 resolved PIE tickets with sufficient text overlap to at least 2 of the 3 existing sample open stories; at least 2 have `mode_used` and `ac_met` populated.
- All new test cases from Testing Strategy (M4a section) pass.
- Existing M3 75/75 tests still pass.
- `RecommendationResponse` schema extended with `similar_tickets`, `supporting_prs`, `evidence_confidence`, `code_analysis_notes`.
- Backward compatibility: existing recommendations without these fields default to `similar_tickets=[]`, `supporting_prs=[]`, `evidence_confidence="none"`, `code_analysis_notes=null`.

**Relevant context:**
- [`backend/services/recommendation_service.py`](backend/services/recommendation_service.py) — `_mode_engine()` is the entry point; `generate()` calls it
- [`backend/models.py`](backend/models.py) — add `ResolvedTicket` and `PREvidence` models here; also add `similar_tickets`, `supporting_prs`, `evidence_confidence`, `code_analysis_notes` columns to `Recommendation`
- [`backend/schemas.py`](backend/schemas.py) — extend `RecommendationResponse` with new fields
- [`backend/services/historical_evidence_service.py`](backend/services/historical_evidence_service.py) — new file; `find_similar(story, db)` and `build_pr_evidence(resolved_tickets)` functions
- `backend/sample_data/resolved_tickets.json` — new file; ≥5 resolved PIE tickets

**Status: `[ ] pending`**

---

### Milestone 4b — PR evidence discovery, LLM analysis, and outcome/session evidence

**Intent:** Enrich PR evidence records with GitHub-sourced metadata (diff, files, test presence, revert detection) and replace pattern-matching with LLM-generated analysis of each PR diff against the new story. Wire `Outcome` and `BobSession` records for similar stories into the mode engine as direct evidence. This is the milestone that enables the full evidence flow: resolved ticket → PR diff → LLM analysis → outcome evidence → session intervention evidence → mode recommendation.

**Acceptance criteria:**
- `PREvidence` ORM model exists with all fields from Core Entities above.
- For each PR URL in `similar_tickets[].linked_prs`, attempt GitHub API call. When `GITHUB_TOKEN` absent or call fails, record `source_warning` and skip enrichment — never silently fail.
- `test_files_present` is set correctly based on file list patterns (fallback) or LLM judgment (preferred).
- `was_reverted` detection via PR title search (no commit-graph traversal required for MVP).
- `backend/services/llm_service.py` created with `analyze_pr(story, pr_diff, resolved_ticket, outcomes, bob_sessions) → LLMAnalysis` interface. Provider selected by `LLM_PROVIDER` env var (`watsonx` or `openai`). When `LLM_API_KEY` absent, returns `None` and records `source_warning`.
- When LLM available, `llm_service.analyze_pr()` is called for each PR and result stored in `PREvidence.diff_summary` and `PREvidence.code_analysis_notes`.
- LLM `mode_signal` and `risk_flags` are incorporated into `mode_evidence[]` and `mode_risks[]` respectively.
- LLM `relevant = false` causes a PR to be excluded from `supporting_prs[]` in the response.
- `Outcome` records for similar stories' `story_id` values are fetched and their `ac_met` / `ac_detail` signals added to `mode_evidence[]` and `mode_risks[]`.
- `BobSession` records for similar stories are fetched and `human_interventions` count signals added to `mode_evidence[]`. Count ≥3 adds a risk item.
- `supporting_prs[]` in `RecommendationResponse` now includes `diff_summary`, `test_files_present`, `was_reverted`, `llm_analysis` fields.
- `was_reverted = True` on any supporting PR adds a "risk" item to `mode_risks[]`.
- When LLM unavailable and `PIE_REPO_PATH` set, fallback shallow code inspection runs and populates `code_analysis_notes`.
- `uncertainty_note` states LLM unavailability when `LLM_API_KEY` not configured.
- `RecommendationResponse` schema extended with `llm_pr_analysis[]`.
- All new test cases from Testing Strategy (M4b section) pass.
- Existing M4a tests still pass.

**Relevant context:**
- `backend/services/llm_service.py` — new file; `analyze_pr()` and provider abstraction
- `backend/services/historical_evidence_service.py` — add `enrich_with_llm()`, `collect_outcome_evidence()`, `collect_session_evidence()` functions
- `backend/services/recommendation_service.py` — `_mode_engine()` extended to consume LLM, outcome, and session evidence items
- `backend/models.py` — `PREvidence` model; `Recommendation` gains `llm_pr_analysis` column
- `backend/schemas.py` — `PREvidence` response schema extended; `RecommendationResponse` gains `llm_pr_analysis`
- `backend/.env.example` — add `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_ENDPOINT`

**Status: `[ ] pending`**

---

### Milestone 4c — Bob session link and evidence capture

**Intent:** Replace the M3 501 stub with a fully working Bob session endpoint. Sessions are created as drafts — either automatically via a Bob stop hook or manually — and must be explicitly confirmed by the user before they link to outcomes. The auto-generated summary pre-fills the UI but is never finalised without review.

**Acceptance criteria:**
- `POST /api/bob-sessions` creates a `BobSession` with `status = "draft"`. Accepts `story_id`, `files_changed`, optional `auto_generated_summary`, optional `hook_triggered_at`, optional `pie_commit_sha`, optional `test_result`.
- `PATCH /api/bob-sessions/{id}/confirm` sets `status = "confirmed"`, writes `summary` from the request body (required, non-empty), stores `human_interventions[]`. If `pie_commit_sha` is present and `PIE_REPO_PATH` is set, runs `git show --stat` and stores `diff_summary`. Returns 422 if `summary` is empty.
- `GET /api/bob-sessions/{story_id}` returns all sessions for the story (both draft and confirmed), ordered by `created_at` descending.
- `POST /api/outcomes` returns 409 when the story has no confirmed session (i.e. all sessions are still draft or none exist) — in addition to the existing mode-approval 409.
- Approval gate (409 on mode pending) preserved and tested end-to-end.
- `BobSessionRequest`, `BobSessionConfirmRequest`, and `BobSessionResponse` schemas added to `schemas.py`.
- `BobSession` model updated with `status`, `auto_generated_summary`, `diff_summary`, `hook_triggered_at` columns.
- All new test cases from Testing Strategy (M4c section) pass.
- Existing M1–M4b tests still pass.

**Status: `[ ] pending`**

---

### Milestone 5a — Requirement-level outcome recording

**Intent:** Replace the M3 501 stub with a fully working outcome endpoint. Record actual execution results at the individual acceptance-criterion level (successful / partial / failed / unverified).

**Acceptance criteria:**
- Schema migration: `Outcome.ac_met` column changed from BOOLEAN to TEXT (`"successful"|"partial"|"failed"|"unverified"`). `Outcome.ac_detail` JSON column added.
- `POST /api/outcomes` stores `test_result`, `build_result`, `review_notes`, `ac_met`, `ac_detail`, `developer_id`, `bob_session_id`, `diff_summary`.
- `GET /api/outcomes/{story_id}` returns all outcomes including `ac_detail`.
- Approval gate (409 when pending) preserved.
- `OutcomeRequest` and `OutcomeResponse` schemas added to `schemas.py`.
- All new test cases from Testing Strategy (M5a section) pass.
- Existing tests still pass (no test uses the boolean `ac_met` directly — verified before migration).

**Status: `[ ] pending`**

---

### Milestone 5b — Comparison and self-learning

**Intent:** Generate a mode + AC comparison when an outcome is recorded. Close the self-learning loop by promoting successful outcomes to the `ResolvedTicket` pool so they feed future recommendations.

**Acceptance criteria:**
- `POST /api/comparisons` accepts `{recommendation_id, outcome_id}`, produces `mode_verdict`, `mode_explanation`, `ac_verdict`, `ac_explanation`. `dev_match_verdict` column exists but is not populated.
- `mode_verdict` rules: `"confirmed"` when outcome mode matches recommendation and `ac_met = "successful"`; `"exceeded"` when `ac_met = "successful"` and actual was more automated than recommended; `"diverged"` otherwise.
- `ac_verdict` mirrors `outcome.ac_met` value (successful / partial / failed / unverified).
- `GET /api/comparisons/{story_id}` returns the comparison.
- **Self-learning:** After a comparison is generated with `ac_verdict = "successful"`, the story is promoted: a new `ResolvedTicket` record is created (or updated if already exists by `jira_key`) with `mode_used`, `ac_met = True`, and `linked_prs` from the `BobSession`. On the *next* call to `POST /api/recommendations` for a story with high text similarity to this one, the promoted record appears in `similar_tickets[]`.
- Partial, failed, and unverified outcomes are stored and appear as risk signals in `mode_risks[]` of future recommendations for similar stories, but do not become positive signals.
- `ComparisonRequest` and `ComparisonResponse` schemas added.
- All new test cases from Testing Strategy (M5b section) pass.
- Existing tests still pass.

**Status: `[ ] pending`**

---

### Milestone 6 — React frontend

**Intent:** Build the four-screen wizard connecting all backend capabilities. The historical evidence panel is the main new UI surface added beyond the original M6 spec.

**Acceptance criteria:**
- **Ticket Prioritization screen:** Ranked list with priority, readiness, blocker indicators. Sample-data banner displayed.
- **Execution Mode screen:** Mode badge, rationale, evidence list (verified/unverified labels), risks, counterevidence, uncertainty note, `ApprovalGate`. **NEW:** `HistoricalEvidencePanel` showing similar tickets (jira_key, title, similarity score, resolution, mode_used) and supporting PRs (title, merged status, files, clickable URL). `evidence_confidence` badge visible. Wizard does not advance until approval given.
- **Link Bob Work screen:** Form for summary, files, commit SHA, human interventions. Submits to `POST /api/bob-sessions`.
- **Outcome & Comparison screen:** Per-AC checkbox/dropdown for individual criterion results. Shows mode verdict and explanation. Shows `ac_verdict` and `ac_explanation`. Shows traceability links: ticket → recommendation → session → outcome → comparison.
- `SampleDataBanner` reused wherever `source === "sample"`.
- App runs via `npm run dev` and connects to the local backend.
- All four wizard screens are functional end-to-end in a manual walkthrough.

**Status: `[ ] pending`**

---

### Milestone 7 — Smoke test and demo readiness

**Acceptance criteria:**
- `scripts/smoke_test.sh` updated to run the full new flow end-to-end without credentials:
  1. Health check
  2. Sample story import
  3. Sample resolved ticket import
  4. `POST /api/recommendations` — assert `similar_tickets` non-empty, `evidence_confidence` ≠ "none", `supporting_prs` non-empty
  5. Approval gate paths (approve, override failure → 422)
  6. `POST /api/bob-sessions` — full creation (not 501)
  7. `POST /api/outcomes` — with `ac_met = "partial"` and `ac_detail`
  8. `POST /api/comparisons` — assert `mode_verdict` and `ac_verdict`
  9. Self-learning: second `POST /api/recommendations` for a similar story after a successful outcome — assert promoted ticket appears in `similar_tickets`
  10. Persistence check: GET after recommendation
- `BOB_USAGE.md` has at least one complete entry reflecting real implemented work.
- `context.md` reflects the final implementation state.
- Demo walkthrough (manual) matches the definition of done below.

**Status: `[ ] pending`**

---

### Milestone 8 — Developer match (DEFERRED — future phase)

> See original plan section "Decision 3: Developer Match" for full spec.

**Status: `[ ] deferred`**

---

## Definition of Done — First End-to-End Demo

1. User opens the app; Ticket Prioritization screen shows a ranked list of open stories (sample, labeled). Priority rationale, readiness signals, and blockers are visible per story.
2. User selects a story; the system generates priority + execution-mode recommendations enriched with historical evidence.
3. **Execution Mode screen:** Mode badge, rationale, evidence list, risks, counterevidence, uncertainty note, `evidence_confidence` badge, and `HistoricalEvidencePanel` (similar tickets + clickable PR links) are displayed. `ApprovalGate` blocks progression.
4. Evidence panel clearly shows which items came from the LLM (`source: "llm_pr_analysis"`), which from outcomes, and which from session interventions — all labeled distinctly.
5. Tech lead approves or overrides the execution mode (separate explicit action).
6. User enters a Bob session summary, lists files changed, optionally provides a commit SHA, and records human intervention notes.
7. Backend fetches the git diff summary (if SHA provided and `PIE_REPO_PATH` set) and stores it.
8. User enters actual results per acceptance criterion (successful / partial / failed / unverified).
9. App displays the comparison: mode verdict + AC verdict + explanation. Traceability links connect ticket → recommendation → session → outcome → comparison.
10. A subsequent recommendation for a similar story incorporates the verified outcome and session interventions as signals (self-learning visible via `similar_tickets`, `evidence_confidence`, and the trust ladder progressing from `human_led` → `collaborative` → `bob_led` across repeated similar tickets).
11. Demo clearly distinguishes what is implemented from what is deferred.

---

## Guardrails — What the System Must Never Do

1. **Never invent evidence.** Every item in `evidence[]`, `similar_tickets[]`, or `supporting_prs[]` must trace to a real DB record, Jira response field, git output, or GitHub API response. If evidence is absent, say so.
2. **Never equate missing experience with inability.** (Applies when Developer Match is built.)
3. **Never rank developers by AI activity.** (Applies when Developer Match is built.)
4. **Never auto-assign work.** `mode_approval_status` is always `"pending"` on creation. Downstream steps return 409 while pending.
5. **Never silently substitute sample data.** Sample data is labeled `source: "sample"` and displayed with `[SAMPLE DATA]` banner.
6. **Never claim stretch success prematurely.** (Applies when Developer Match is built.)
7. **Never use story points for recommendations.** `story_points` is imported metadata only.
8. **Never allow an override without a reason.** `override_reason` must be non-empty; 422 otherwise.
9. **Never claim self-learning without a closed loop.** Storing outcomes alone does not constitute learning. The loop is only closed when verified outcomes feed back into the similarity search and change future recommendation scores. The `evidence_confidence` field makes the loop observable.
10. **Never promote unverified or failed outcomes as positive signals.** Only `ac_verdict = "successful"` outcomes are promoted to the resolved ticket pool as positive signals. Partial and failed outcomes are stored as risk signals only.
11. **Never let the LLM directly set the mode.** The LLM produces evidence items and risk flags that feed the rule engine's score. The rule engine makes the final `bob_led` / `collaborative` / `human_led` call. LLM output is always labeled `source: "llm_pr_analysis"` in evidence items so it is auditable and distinguishable from rule-based signals.
12. **Never silently skip LLM analysis.** When `LLM_API_KEY` is absent or an LLM call fails, `source_warning` must be recorded and `uncertainty_note` must state that LLM analysis was unavailable. The caller must display a visible warning.

---

## Single Best Next Task

**Milestone 4a — Historical ticket retrieval and semantic similarity.**

It is the foundation for all subsequent historical-evidence features (PR evidence, LLM analysis, outcome/session evidence, self-learning). It produces an immediately demonstrable change to the `POST /api/recommendations` response (new `similar_tickets` and `evidence_confidence` fields) that is visible in both the API and the future UI without requiring any UI changes. All subsequent milestones build on its `ResolvedTicket` data model and the `historical_evidence_service` interface — which is designed so that M4b can layer LLM analysis, outcome evidence, and session intervention signals on top without changing the recommendation service's public API. It can be implemented and tested with sample data, without live Jira, GitHub, or LLM credentials.
