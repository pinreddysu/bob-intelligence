"""
Pydantic request/response schemas — Milestone 2.

Covers: Story import, story listing, developer profile listing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Story schemas
# ---------------------------------------------------------------------------

class StoryImportRequest(BaseModel):
    """
    Request body for POST /api/stories/import.

    Exactly one of `jira_key` or `import_source="sample"` must be provided.
    """

    import_source: Literal["jira", "sample"] = Field(
        ...,
        description=(
            "'jira' — fetch a single story from Jira using `jira_key`. "
            "'sample' — import all sample stories from the built-in sample data."
        ),
    )
    jira_key: str | None = Field(
        default=None,
        description="Jira issue key (e.g. 'PIE-42'). Required when import_source='jira'.",
    )

    model_config = {"json_schema_extra": {"examples": [
        {"import_source": "jira", "jira_key": "PIE-42"},
        {"import_source": "sample"},
    ]}}


class StoryResponse(BaseModel):
    """A single story as returned by the API."""

    id: str
    jira_key: str | None
    title: str
    description: str | None
    acceptance_criteria: str | None
    # story_points is display metadata only — never used for recommendations.
    story_points: int | None
    labels: list[Any]
    priority: str | None
    status: str | None
    assignee: str | None
    blockers: list[Any]
    linked_prs: list[Any]
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryImportResponse(BaseModel):
    """
    Response for POST /api/stories/import.

    Always includes source_status so the caller can distinguish live Jira
    data from sample data and surface warnings where appropriate.
    """

    stories: list[StoryResponse]
    source_status: str = Field(
        description=(
            "'jira' — imported from live Jira. "
            "'sample_import' — imported from built-in sample data. "
            "'credentials_missing' — Jira import requested but credentials not set. "
            "'jira_error' — Jira API returned an error."
        )
    )
    source_warning: str | None = Field(
        default=None,
        description="Human-readable warning when source_status is not 'jira'.",
    )
    skipped_duplicates: int = Field(
        default=0,
        description="Number of stories skipped because they already exist in the DB.",
    )


class StoryListResponse(BaseModel):
    """Response for GET /api/stories."""

    stories: list[StoryResponse]
    total: int


# ---------------------------------------------------------------------------
# DeveloperProfile schemas
# ---------------------------------------------------------------------------

class DeveloperProfileResponse(BaseModel):
    """A single developer profile as returned by the API."""

    id: str
    display_name: str
    jira_account_id: str | None
    verified_skills: list[Any]
    verified_pr_count: int
    verified_review_count: int
    recent_domains: list[Any]
    availability_note: str | None
    source: str

    model_config = {"from_attributes": True}


class DeveloperProfileListResponse(BaseModel):
    """Response for GET /api/developer-profiles."""

    profiles: list[DeveloperProfileResponse]
    total: int
