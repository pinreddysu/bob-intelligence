"""
/api/recommendations router — Milestone 3.

Endpoints:
  POST  /api/recommendations                       Generate priority + mode recommendation.
  GET   /api/recommendations/{id}                  Get recommendation by ID.
  PATCH /api/recommendations/{id}/mode-approve     Tech lead approves execution mode.
  PATCH /api/recommendations/{id}/mode-override    Tech lead overrides execution mode.

Approval gate rules (from plan):
  - mode_approval_status starts as "pending" on creation.
  - PATCH .../mode-approve  requires non-empty `approved_by`.
  - PATCH .../mode-override requires non-empty `approved_by` + `override_reason`; 422 if missing.
  - Downstream endpoints (bob-sessions, outcomes) return 409 while status is "pending".
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Recommendation, Story
from backend.schemas import (
    ModeApproveRequest,
    ModeOverrideRequest,
    RecommendationRequest,
    RecommendationResponse,
)
from backend.services import recommendation_service

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

_VALID_MODES = {"bob_led", "collaborative", "human_led"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# POST /api/recommendations
# ---------------------------------------------------------------------------

@router.post("", response_model=RecommendationResponse, status_code=201)
def create_recommendation(
    body: RecommendationRequest,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """
    Generate priority and execution-mode recommendations for a story.

    - story_points is never used.
    - mode_approval_status is always "pending" on the new record.
    - Any existing "pending" recommendation for this story is superseded.
    """
    story = db.query(Story).filter(Story.id == body.story_id).first()
    if not story:
        raise HTTPException(
            status_code=404,
            detail=f"Story '{body.story_id}' not found.",
        )

    rec = recommendation_service.generate(story, db)
    return RecommendationResponse.model_validate(rec)


# ---------------------------------------------------------------------------
# GET /api/recommendations/{rec_id}
# ---------------------------------------------------------------------------

@router.get("/{rec_id}", response_model=RecommendationResponse)
def get_recommendation(
    rec_id: str,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Return a single recommendation by its ID."""
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation '{rec_id}' not found.",
        )
    return RecommendationResponse.model_validate(rec)


# ---------------------------------------------------------------------------
# PATCH /api/recommendations/{rec_id}/mode-approve
# ---------------------------------------------------------------------------

@router.patch("/{rec_id}/mode-approve", response_model=RecommendationResponse)
def mode_approve(
    rec_id: str,
    body: ModeApproveRequest,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """
    Tech lead approves the execution-mode recommendation.

    - Sets mode_approval_status to "approved".
    - Records mode_approved_by and mode_approved_at.
    - Returns 404 if the recommendation does not exist.
    - approved_by must be non-empty (enforced by schema min_length=1).
    """
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation '{rec_id}' not found.",
        )

    rec.mode_approval_status = "approved"
    rec.mode_approved_by = body.approved_by
    rec.mode_approved_at = _now()
    db.commit()
    db.refresh(rec)
    return RecommendationResponse.model_validate(rec)


# ---------------------------------------------------------------------------
# PATCH /api/recommendations/{rec_id}/mode-override
# ---------------------------------------------------------------------------

@router.patch("/{rec_id}/mode-override", response_model=RecommendationResponse)
def mode_override(
    rec_id: str,
    body: ModeOverrideRequest,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """
    Tech lead overrides the execution-mode recommendation.

    - Both approved_by and override_reason must be non-empty (422 otherwise).
    - Sets mode_approval_status to "overridden".
    - Records mode_approved_by, mode_approved_at, and mode_override_reason.
    - Optionally updates mode if a new mode is supplied in the body.
    - Returns 404 if the recommendation does not exist.
    """
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation '{rec_id}' not found.",
        )

    # Schema enforces min_length=1 for both fields; this is a belt-and-suspenders check.
    if not body.override_reason or not body.override_reason.strip():
        raise HTTPException(
            status_code=422,
            detail="override_reason must be a non-empty string.",
        )
    if not body.approved_by or not body.approved_by.strip():
        raise HTTPException(
            status_code=422,
            detail="approved_by must be a non-empty string.",
        )

    # Optional mode update
    if body.mode is not None:
        if body.mode not in _VALID_MODES:
            raise HTTPException(
                status_code=422,
                detail=f"mode must be one of {sorted(_VALID_MODES)!r}.",
            )
        rec.mode = body.mode

    rec.mode_approval_status = "overridden"
    rec.mode_approved_by = body.approved_by
    rec.mode_approved_at = _now()
    rec.mode_override_reason = body.override_reason.strip()
    db.commit()
    db.refresh(rec)
    return RecommendationResponse.model_validate(rec)
