"""
Bob Intelligence — FastAPI application entry point.

Milestone 1: health endpoint only.
Milestones 2-7 will register additional routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bob Intelligence",
    description="Explainable Bob/Collaborative/Human-led execution recommendations for Jira stories.",
    version="0.1.0",
)

# Allow the Vite dev server (default port 5173) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    """Liveness check — returns 200 OK when the backend is running."""
    return {"status": "ok"}
