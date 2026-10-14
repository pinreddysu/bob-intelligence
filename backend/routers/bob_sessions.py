"""
/api/bob-sessions router — Milestone 4 (stub with Milestone 3 gate).

Milestone 3 gate: POST /api/bob-sessions returns 409 Conflict when the
story's most recent recommendation has mode_approval_status == "pending".

Milestone 4 will add full session creation and retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Recommendation, Story

router = APIRouter(prefix="/api/bob-sessions", tags=["bob-sessions"])


def _check_mode_approved(story_id: str, db: Session) -> None:
    """
    Raise 409 if the most recent recommendation for the story has
    mode_approval_status == "pending".

    If no recommendation exists at all, the gate is not triggered —
    the recommendation step has simply not been run yet.
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
                f"(recommendation id: {latest_rec.id}) before a Bob session can be linked."
            ),
        )


# ---------------------------------------------------------------------------
# POST /api/bob-sessions  — Milestone 4 stub (gate enforced in Milestone 3)
# ---------------------------------------------------------------------------

class _BobSessionStubRequest(BaseModel):
    story_id: str = Field(..., description="ID of the story this Bob session is linked to.")
    summary: str = Field(..., min_length=1)
    files_changed: list[str] = Field(default_factory=list)
    pie_commit_sha: str | None = Field(default=None)


@router.post("", status_code=201)
def create_bob_session(
    body: _BobSessionStubRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Create a Bob session link.

    Returns 409 Conflict when the story's recommendation has mode_approval_status='pending'.
    Full implementation is in Milestone 4.
    """
    # Validate story exists
    story = db.query(Story).filter(Story.id == body.story_id).first()
    if not story:
        raise HTTPException(
            status_code=404,
            detail=f"Story '{body.story_id}' not found.",
        )

    # Gate: reject if execution mode is not yet approved
    _check_mode_approved(body.story_id, db)

    # Milestone 4 will implement actual session persistence here.
    # Return a 501 to signal the endpoint exists but is not yet fully implemented.
    raise HTTPException(
        status_code=501,
        detail=(
            "Bob session creation is implemented in Milestone 4. "
            "Approval gate is active and enforced."
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/bob-sessions/{story_id}  — Milestone 4 stub
# ---------------------------------------------------------------------------

@router.get("/{story_id}")
def get_bob_sessions(
    story_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve Bob sessions for a story (full implementation in Milestone 4)."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(
            status_code=404,
            detail=f"Story '{story_id}' not found.",
        )
    raise HTTPException(
        status_code=501,
        detail="Bob session retrieval is implemented in Milestone 4.",
    )
