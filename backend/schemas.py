"""
Pydantic request/response schemas — Milestones 2, 3, and 4a.

Covers: Story import, story listing, developer profile listing,
        recommendation generation, approval/override,
        resolved ticket import/listing (M4a).
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


# ---------------------------------------------------------------------------
# Recommendation schemas
# ---------------------------------------------------------------------------

class RecommendationRequest(BaseModel):
    """
    Request body for POST /api/recommendations.
    """
    story_id: str = Field(..., description="ID of the story to generate recommendations for.")

    model_config = {"json_schema_extra": {"examples": [
        {"story_id": "some-uuid-here"},
    ]}}


class EvidenceItem(BaseModel):
    source: str
    description: str
    verified: bool = True


class RiskItem(BaseModel):
    description: str
    severity: str  # "low" | "medium" | "high"


class CounterEvidenceItem(BaseModel):
    description: str


class SimilarTicketItem(BaseModel):
    """A single similar resolved ticket as returned in recommendation responses."""

    jira_key: str
    title: str
    similarity_score: float
    resolution: str | None
    mode_used: str | None
    ac_met: bool | None


class SupportingPRItem(BaseModel):
    """A PR URL extracted from a resolved ticket's linked_prs list."""

    url: str
    merged: bool | None = None
    files_changed: list[Any] = []
    title: str | None = None


class RecommendationResponse(BaseModel):
    """A full recommendation record as returned by the API."""

    id: str
    story_id: str

    # Ticket prioritization
    priority_rank: int | None
    priority_rationale: str | None
    priority_evidence: list[Any]

    # Execution mode
    mode: str | None  # "bob_led" | "collaborative" | "human_led"
    mode_rationale: str | None
    mode_evidence: list[Any]
    mode_risks: list[Any]
    mode_counterevidence: list[Any]

    # Mode approval gate
    mode_approval_status: str  # "pending" | "approved" | "overridden"
    mode_approved_by: str | None
    mode_approved_at: datetime | None
    mode_override_reason: str | None

    # Developer match — DEFERRED; present as null/empty in MVP
    suggested_developer: str | None
    dev_match_rationale: str | None
    dev_match_evidence: list[Any]
    dev_match_risks: list[Any]
    is_stretch_assignment: bool
    stretch_support_plan: str | None
    dev_match_approval_status: str
    dev_match_approved_by: str | None
    dev_match_approved_at: datetime | None
    dev_match_override_reason: str | None

    # Historical evidence (M4a) — defaults preserve backward compatibility
    similar_tickets: list[Any] = []
    supporting_prs: list[Any] = []
    evidence_confidence: str = "none"   # "high"|"medium"|"low"|"none"
    code_analysis_notes: str | None = None  # populated in M4b

    # Shared
    uncertainty_note: str | None
    status: str  # "pending" | "superseded"
    created_at: datetime

    model_config = {"from_attributes": True}


class ModeApproveRequest(BaseModel):
    """
    Request body for PATCH /api/recommendations/{id}/mode-approve.
    approved_by must be non-empty.
    """
    approved_by: str = Field(
        ...,
        min_length=1,
        description="Identifier of the tech lead approving the execution mode.",
    )


class ModeOverrideRequest(BaseModel):
    """
    Request body for PATCH /api/recommendations/{id}/mode-override.
    Both approved_by and override_reason are required and must be non-empty.
    """
    approved_by: str = Field(
        ...,
        min_length=1,
        description="Identifier of the tech lead overriding the execution mode.",
    )
    override_reason: str = Field(
        ...,
        min_length=1,
        description="Required non-empty reason explaining why the recommended mode is overridden.",
    )
    mode: str | None = Field(
        default=None,
        description="Optional new mode to set when overriding ('bob_led'|'collaborative'|'human_led').",
    )


# ---------------------------------------------------------------------------
# ResolvedTicket schemas (M4a)
# ---------------------------------------------------------------------------

class ResolvedTicketResponse(BaseModel):
    """A single resolved ticket as returned by the API."""

    id: str
    jira_key: str
    title: str
    description: str | None
    resolution: str | None
    labels: list[Any]
    linked_prs: list[Any]
    files_changed: list[Any]
    mode_used: str | None
    ac_met: bool | None
    was_reverted: bool
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolvedTicketImportRequest(BaseModel):
    """
    Request body for POST /api/resolved-tickets/import.

    source="sample" loads from sample_data/resolved_tickets.json.
    source="jira"   calls the Jira search API (JQL: project=PIE AND status=Done).
    """

    source: Literal["sample", "jira"] = Field(
        ...,
        description=(
            "'sample' — import from built-in sample data. "
            "'jira' — fetch resolved tickets from Jira using configured JQL."
        ),
    )

    model_config = {"json_schema_extra": {"examples": [
        {"source": "sample"},
        {"source": "jira"},
    ]}}


class ResolvedTicketImportResponse(BaseModel):
    """Response for POST /api/resolved-tickets/import."""

    tickets: list[ResolvedTicketResponse]
    source_status: str = Field(
        description=(
            "'sample_import' — loaded from built-in sample data. "
            "'jira' — fetched from live Jira. "
            "'credentials_missing' — Jira import requested but credentials absent. "
            "'jira_error' — Jira API returned an error."
        )
    )
    source_warning: str | None = None
    skipped_duplicates: int = 0


class ResolvedTicketListResponse(BaseModel):
    """Response for GET /api/resolved-tickets."""

    tickets: list[ResolvedTicketResponse]
    total: int
