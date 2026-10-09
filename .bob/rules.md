# Bob Intelligence — Persistent Rules for IBM Bob

These rules apply to all Bob tasks on this repository.

## Cost and scope

- Conserve Bob coins. Use focused, single-milestone tasks. Avoid redundant file exploration.
- Inspect relevant files before changing code — never speculate about content you have not read.
- Keep changes small and scoped to the approved task. Do not add features, refactors, or abstractions beyond what was asked.
- Reuse decisions already established in `context.md` and `bob-intelligence-plan.md` without relitigating them.

## Repository boundaries

- Keep **Bob Intelligence** and **PIE** (`Ai-stock-intelligence-platform-hackathon`) as completely separate repositories. Do not mix code, commits, or files between them.
- Never reference PIE's internal implementation from Bob Intelligence code except via the configured `PIE_REPO_PATH` environment variable.

## Integrity

- Never claim an integration or feature works without verification. Distinguish implemented, tested, and unverified functionality explicitly.
- Run relevant tests and report actual results. Do not invent test outcomes.
- Do not fabricate historical data, engineering outcomes, Bob telemetry, token counts, or prediction accuracy.
- Sample data must always be labeled `source: "sample"` and displayed with a visible banner. Never present it as real engineering history.
- Keep secrets (API tokens, credentials) out of source control. Use `.env` (gitignored) copied from `.env.example`.

## Implementation discipline

- Update `context.md` after each milestone is completed with accurate implementation status.
- Update `BOB_USAGE.md` after meaningful, verified tasks — not after every small action. Record actual results, not intentions.
- Update `rules.md` only when a persistent rule genuinely needs to change.
- Do not begin implementation work during a planning task. Stop after the plan and wait for approval.
