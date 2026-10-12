"""
Bob Intelligence — FastAPI application entry point.

Milestone 1: health endpoint.
Milestone 2: ORM init, stories router, developer-profiles router.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import stories
from backend.routers import developer_profiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup (no-op if they already exist)."""
    init_db()
    yield


app = FastAPI(
    title="Bob Intelligence",
    description="Explainable Bob/Collaborative/Human-led execution recommendations for Jira stories.",
    version="0.2.0",
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


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    """Liveness check — returns 200 OK when the backend is running."""
    return {"status": "ok"}
