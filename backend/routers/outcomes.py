"""
/api/outcomes and /api/comparisons routers — Milestone 5 (stub with Milestone 3 gate).

Milestone 3 gate: POST /api/outcomes returns 409 Conflict when the story's
most recent recommendation has mode_approval_status == "pending".

Full outcome and comparison implementation is in Milestone 5.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Recommendation, Story

router = APIRouter(tags=["outcomes"])


def _check_mode_approved(story_id: str, db: Session) -> None:
    """
    Raise 409 if the most recent recommendation for the story has
    mode_approval_status == "pending".
    """
    latest_rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.story_id == story_id,
            Recommendation.status == "pending",
        )
        .order_by(Recommendation.created_at.desc())
        .first()
    )
    if latest_rec is not None and latest_rec.mode_approval_status == "pending":
        raise HTTPException(
            status_code=409,
            detail=(
                "Execution-mode recommendation has not been approved. "
                "A tech lead must approve or override the execution mode "
                f"(recommendation id: {latest_rec.id}) before an outcome can be recorded."
            ),
        )


# ---------------------------------------------------------------------------
# POST /api/outcomes  — Milestone 5 stub (gate enforced in Milestone 3)
# ---------------------------------------------------------------------------

class _OutcomeStubRequest(BaseModel):
    story_id: str = Field(..., description="ID of the story this outcome is for.")
    test_result: str | None = Field(default=None)
    build_result: str | None = Field(default=None)
    review_notes: str | None = Field(default=None)
    ac_met: bool | None = Field(default=None)
    developer_id: str | None = Field(default=None)
    bob_session_id: str | None = Field(default=None)


@router.post("/api/outcomes", status_code=201)
def create_outcome(
    body: _OutcomeStubRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Record an outcome for a story.

    Returns 409 Conflict when the story's recommendation has mode_approval_status='pending'.
    Full implementation is in Milestone 5.
    """
    story = db.query(Story).filter(Story.id == body.story_id).first()
    if not story:
        raise HTTPException(
            status_code=404,
            detail=f"Story '{body.story_id}' not found.",
        )

    _check_mode_approved(body.story_id, db)

    raise HTTPException(
        status_code=501,
        detail=(
            "Outcome recording is implemented in Milestone 5. "
            "Approval gate is active and enforced."
        ),
    )


@router.get("/api/outcomes/{story_id}")
def get_outcomes(
    story_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get outcomes for a story (full implementation in Milestone 5)."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(
            status_code=404,
            detail=f"Story '{story_id}' not found.",
        )
    raise HTTPException(
        status_code=501,
        detail="Outcome retrieval is implemented in Milestone 5.",
    )


@router.post("/api/comparisons", status_code=201)
def create_comparison(db: Session = Depends(get_db)) -> dict:
    """Generate comparison (full implementation in Milestone 5)."""
    raise HTTPException(
        status_code=501,
        detail="Comparison generation is implemented in Milestone 5.",
    )


@router.get("/api/comparisons/{story_id}")
def get_comparisons(
    story_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get comparisons for a story (full implementation in Milestone 5)."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(
            status_code=404,
            detail=f"Story '{story_id}' not found.",
        )
    raise HTTPException(
        status_code=501,
        detail="Comparison retrieval is implemented in Milestone 5.",
    )
