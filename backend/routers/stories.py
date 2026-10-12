"""
/api/stories router — Milestone 2.

Endpoints:
  GET  /api/stories            List all imported stories.
  POST /api/stories/import     Import a story from Jira or from sample data.
  GET  /api/stories/{id}       Get a single story by ID.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Story
from backend.schemas import (
    StoryImportRequest,
    StoryImportResponse,
    StoryListResponse,
    StoryResponse,
)
from backend.services import jira_service

router = APIRouter(prefix="/api/stories", tags=["stories"])


# ---------------------------------------------------------------------------
# GET /api/stories
# ---------------------------------------------------------------------------

@router.get("", response_model=StoryListResponse)
def list_stories(db: Session = Depends(get_db)) -> StoryListResponse:
    """Return all imported stories ordered by created_at descending."""
    stories = db.query(Story).order_by(Story.created_at.desc()).all()
    return StoryListResponse(
        stories=[StoryResponse.model_validate(s) for s in stories],
        total=len(stories),
    )


# ---------------------------------------------------------------------------
# POST /api/stories/import
# ---------------------------------------------------------------------------

@router.post("/import", response_model=StoryImportResponse, status_code=201)
def import_stories(
    body: StoryImportRequest,
    db: Session = Depends(get_db),
) -> StoryImportResponse:
    """
    Import one or more stories.

    - import_source='jira':   fetch the story identified by `jira_key` from Jira REST v3.
                              Returns an error response (not sample data) when credentials
                              are absent or the Jira request fails.
    - import_source='sample': import all built-in sample stories.  Idempotent — stories
                              already in the DB (matched by jira_key) are skipped.
    """
    if body.import_source == "jira":
        if not body.jira_key or not body.jira_key.strip():
            raise HTTPException(
                status_code=422,
                detail="jira_key is required when import_source is 'jira'.",
            )
        return _import_from_jira(body.jira_key.strip(), db)

    # import_source == "sample"
    return _import_sample(db)


def _import_from_jira(jira_key: str, db: Session) -> StoryImportResponse:
    result = jira_service.fetch_from_jira(jira_key)
    source_status: str = result["source_status"]
    source_warning: str | None = result["source_warning"]
    story_data = result["story_data"]

    if story_data is None:
        # Jira credentials missing or request failed — return error, NOT sample data.
        return StoryImportResponse(
            stories=[],
            source_status=source_status,
            source_warning=source_warning,
            skipped_duplicates=0,
        )

    # Deduplicate by jira_key
    existing = (
        db.query(Story).filter(Story.jira_key == story_data["jira_key"]).first()
        if story_data.get("jira_key")
        else None
    )
    if existing:
        return StoryImportResponse(
            stories=[StoryResponse.model_validate(existing)],
            source_status=source_status,
            source_warning=source_warning,
            skipped_duplicates=1,
        )

    story = Story(**story_data)
    db.add(story)
    db.commit()
    db.refresh(story)

    return StoryImportResponse(
        stories=[StoryResponse.model_validate(story)],
        source_status=source_status,
        source_warning=source_warning,
        skipped_duplicates=0,
    )


def _import_sample(db: Session) -> StoryImportResponse:
    sample_stories = jira_service.load_sample_stories()
    imported: list[Story] = []
    skipped = 0

    for data in sample_stories:
        jira_key = data.get("jira_key")
        # Deduplicate: skip if a story with the same jira_key already exists.
        if jira_key:
            existing = db.query(Story).filter(Story.jira_key == jira_key).first()
            if existing:
                skipped += 1
                continue

        story = Story(**{k: v for k, v in data.items() if k != "id"})
        db.add(story)
        imported.append(story)

    db.commit()
    for story in imported:
        db.refresh(story)

    return StoryImportResponse(
        stories=[StoryResponse.model_validate(s) for s in imported],
        source_status="sample_import",
        source_warning=(
            "Stories imported from built-in sample data. "
            "These are clearly labeled source='sample' and are not from a live Jira instance."
        ),
        skipped_duplicates=skipped,
    )


# ---------------------------------------------------------------------------
# GET /api/stories/{story_id}
# ---------------------------------------------------------------------------

@router.get("/{story_id}", response_model=StoryResponse)
def get_story(story_id: str, db: Session = Depends(get_db)) -> StoryResponse:
    """Return a single story by its ID."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail=f"Story '{story_id}' not found.")
    return StoryResponse.model_validate(story)
