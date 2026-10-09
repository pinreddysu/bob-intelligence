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
| Database | In-memory SQLite | (via SQLAlchemy) |
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
     ├── /api/stories         → jira_service  (Jira REST v3 or sample fallback)
     ├── /api/recommendations → recommendation_service (rule engine)
     ├── /api/bob-sessions    → SQLite (manual explicit link)
     └── /api/outcomes        → evidence_service + SQLite
```

No automatic Bob session telemetry. Bob sessions are created by explicit POST.

## Repository Structure

```
bob-intelligence/
├── backend/
│   ├── main.py               FastAPI app + /api/health
│   ├── database.py           SQLAlchemy engine + session
│   ├── models.py             ORM models (Milestone 2)
│   ├── schemas.py            Pydantic schemas (Milestone 2+)
│   ├── routers/              One module per resource
│   ├── services/             jira, recommendation, evidence
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/            4 wizard-step pages
│   │   ├── api/              Typed fetch wrappers
│   │   └── main.tsx          Router
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── scripts/
│   └── smoke_test.sh
├── context.md
├── rules.md
├── BOB_USAGE.md
└── bob-intelligence-plan.md
```

## Implementation Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| 1 — Scaffold + docs baseline | ✅ Complete | Health endpoint verified. Smoke test exits 0. pydantic pinned to 2.14.0 for Python 3.14 wheel compatibility. |
| 2 — Data layer + story import | ⬜ Pending | |
| 3 — Recommendation engine | ⬜ Pending | |
| 4 — Bob session link + evidence | ⬜ Pending | |
| 5 — Outcome + comparison | ⬜ Pending | |
| 6 — React frontend | ⬜ Pending | Placeholder pages exist |
| 7 — Smoke test + demo readiness | ⬜ Pending | |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Navigation | Wizard-style (4 linear steps) | Demo clarity |
| Sample story | PIE-domain ("Add portfolio rebalancing endpoint") | Realistic domain context |
| Jira fallback | Sample data when credentials absent | Demo works without credentials |
| Recommendation logic | Pure rule engine | Transparent, no invented probabilities |
| Bob session capture | Explicit POST (no telemetry assumed) | Confirmed: Bob has no session-history API |
| DB | In-memory SQLite | Zero-config MVP; swap URL to persist |

## Known Limitations

- In-memory SQLite: all data lost on backend restart (intentional for MVP).
- Bob session data is manually entered; no automatic capture from Bob.
- Jira custom field keys (story points, AC) vary by instance — must validate during Milestone 2.
- Frontend pages are placeholder shells; real UI implemented in Milestone 6.
- Git evidence capture (Milestone 4) unverified until tested with real PIE repo path.

## Next Steps

1. **Milestone 2** — Implement ORM models, `POST /api/stories/import`, `GET /api/stories`, Jira service with fallback.
2. Validate Jira field keys on a real story before writing the parser.
