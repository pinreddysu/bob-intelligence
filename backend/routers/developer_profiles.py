"""
/api/developer-profiles router — Milestone 2.

Endpoints:
  GET  /api/developer-profiles   List all developer profiles.
  POST /api/developer-profiles/import-sample  Import sample developer profiles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import DeveloperProfile
from backend.schemas import DeveloperProfileListResponse, DeveloperProfileResponse
from backend.services import jira_service

router = APIRouter(prefix="/api/developer-profiles", tags=["developer-profiles"])


@router.get("", response_model=DeveloperProfileListResponse)
def list_developer_profiles(db: Session = Depends(get_db)) -> DeveloperProfileListResponse:
    """Return all developer profiles."""
    profiles = db.query(DeveloperProfile).order_by(DeveloperProfile.display_name).all()
    return DeveloperProfileListResponse(
        profiles=[DeveloperProfileResponse.model_validate(p) for p in profiles],
        total=len(profiles),
    )


@router.post("/import-sample", response_model=DeveloperProfileListResponse, status_code=201)
def import_sample_profiles(db: Session = Depends(get_db)) -> DeveloperProfileListResponse:
    """
    Import sample developer profiles.  Idempotent — profiles already present
    (matched by jira_account_id) are skipped.
    """
    sample_profiles = jira_service.load_sample_developer_profiles()
    imported: list[DeveloperProfile] = []

    for data in sample_profiles:
        account_id = data.get("jira_account_id")
        if account_id:
            existing = (
                db.query(DeveloperProfile)
                .filter(DeveloperProfile.jira_account_id == account_id)
                .first()
            )
            if existing:
                continue
        profile = DeveloperProfile(**{k: v for k, v in data.items() if k != "id"})
        db.add(profile)
        imported.append(profile)

    db.commit()
    for p in imported:
        db.refresh(p)

    return DeveloperProfileListResponse(
        profiles=[DeveloperProfileResponse.model_validate(p) for p in imported],
        total=len(imported),
    )
