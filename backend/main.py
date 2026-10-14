"""
Bob Intelligence — FastAPI application entry point.

Milestone 1: health endpoint.
Milestone 2: ORM init, stories router, developer-profiles router.
Milestone 3: recommendations router (priority + mode), approval/override endpoints,
             downstream 409 gates on bob-sessions and outcomes.
Milestone 4a: resolved-tickets router (import + list).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import stories
from backend.routers import developer_profiles
from backend.routers import recommendations
from backend.routers import bob_sessions
from backend.routers import outcomes
from backend.routers import resolved_tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup (no-op if they already exist)."""
    init_db()
    yield


app = FastAPI(
    title="Bob Intelligence",
    description="Explainable Bob/Collaborative/Human-led execution recommendations for Jira stories.",
    version="0.4.0",
    lifespan=lifespan,
)

# Allow the Vite dev server (default port 5173) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(stories.router)
app.include_router(developer_profiles.router)
app.include_router(recommendations.router)
app.include_router(bob_sessions.router)
app.include_router(outcomes.router)
app.include_router(resolved_tickets.router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    """Liveness check — returns 200 OK when the backend is running."""
    return {"status": "ok"}
