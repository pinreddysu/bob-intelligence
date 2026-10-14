"""
ORM models — Milestones 2, 3, 4a.

Entities:
  Story, Recommendation, DeveloperProfile, BobSession, Outcome, Comparison,
  ResolvedTicket (NEW in M4a)

Schema note (approval status contradiction resolved):
  The plan specified a single `approval_status` field on Recommendation, but the
  product requires independent approval/override tracking for *two separate decisions*:
    - Execution Mode  (blocks Bob-session link / outcome steps)
    - Developer Match (same gate, independently recorded)
  Ticket Prioritization is advisory only — no approval gate needed.

  Resolution (minimal schema addition): the single `approval_status` field is
  replaced by:
    mode_approval_status      — "pending" | "approved" | "overridden"
    mode_approved_by          — tech-lead id (required on approve/override)
    mode_approved_at          — timestamp
    mode_override_reason      — required (non-empty) when mode_approval_status="overridden"
    dev_match_approval_status — "pending" | "approved" | "overridden"
    dev_match_approved_by
    dev_match_approved_at
    dev_match_override_reason

  This is the smallest change that allows each decision to be approved or
  overridden independently without a data-model rewrite in future milestones.

M4a additions:
  - ResolvedTicket ORM model added below Comparison.
  - Recommendation gains: similar_tickets, supporting_prs, evidence_confidence,
    code_analysis_notes (all nullable/defaulted for backward compatibility).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Story
# ---------------------------------------------------------------------------

class Story(Base):
    """A Jira story imported into the system (or created from sample data)."""

    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    jira_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    # story_points is imported metadata ONLY — must not influence any recommendation.
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    labels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # priority as imported from Jira: "highest"|"high"|"medium"|"low"|"lowest"
    priority: Mapped[str | None] = mapped_column(String, nullable=True)
    # Jira workflow status, e.g. "To Do", "In Progress"
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    # Raw Jira assignee string — not a FK to DeveloperProfile
    assignee: Mapped[str | None] = mapped_column(String, nullable=True)
    # List of blocking issue keys (e.g. ["PIE-10", "PIE-11"])
    blockers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # List of PR URLs linked in Jira
    linked_prs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # "jira" | "sample"
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    bob_sessions: Mapped[list["BobSession"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    outcomes: Mapped[list["Outcome"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# DeveloperProfile
# ---------------------------------------------------------------------------

class DeveloperProfile(Base):
    """Verified profile of a developer.  No AI-activity scores."""

    __tablename__ = "developer_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    jira_account_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Skill tags drawn from verified evidence only (merged PRs, recorded reviews, outcomes)
    verified_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    verified_pr_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # e.g. ["api", "frontend", "infra"]
    recent_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    availability_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "jira" | "sample"
    source: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    outcomes: Mapped[list["Outcome"]] = relationship(back_populates="developer")


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

class Recommendation(Base):
    """
    Combined recommendation record covering all three decisions for a story.

    Approval status is tracked independently for execution-mode and
    developer-match decisions (the two that have approval gates).
    Ticket prioritization is advisory and has no gate.
    """

    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(
        String, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ── Ticket prioritization (advisory — no approval gate) ──────────────────
    priority_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # ── Execution mode ────────────────────────────────────────────────────────
    mode: Mapped[str | None] = mapped_column(String, nullable=True)  # "bob_led"|"collaborative"|"human_led"
    mode_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    mode_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    mode_counterevidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Mode approval gate (independent of dev-match approval)
    mode_approval_status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )  # "pending"|"approved"|"overridden"
    mode_approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    mode_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mode_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── Developer match ───────────────────────────────────────────────────────
    suggested_developer: Mapped[str | None] = mapped_column(
        String, ForeignKey("developer_profiles.id", ondelete="SET NULL"), nullable=True
    )
    dev_match_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    dev_match_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dev_match_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_stretch_assignment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    stretch_support_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Dev-match approval gate (independent of mode approval)
    dev_match_approval_status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )  # "pending"|"approved"|"overridden"
    dev_match_approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    dev_match_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dev_match_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── Historical evidence (M4a) ─────────────────────────────────────────────
    # List of {jira_key, title, similarity_score, resolution, mode_used, ac_met}
    similar_tickets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Union of linked_prs from similar tickets: list of {url, title, merged, files_changed}
    supporting_prs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # "high" (≥3 similar with outcomes) | "medium" (1–2) | "low" (similar, no outcomes) | "none"
    evidence_confidence: Mapped[str] = mapped_column(
        String, nullable=False, default="none"
    )
    # Populated in M4b; null in M4a
    code_analysis_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Shared ────────────────────────────────────────────────────────────────
    uncertainty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "pending" | "superseded"
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    story: Mapped["Story"] = relationship(back_populates="recommendations")
    comparisons: Mapped[list["Comparison"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# BobSession
# ---------------------------------------------------------------------------

class BobSession(Base):
    """Manually recorded evidence of Bob-assisted work on a story."""

    __tablename__ = "bob_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(
        String, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    files_changed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    pie_commit_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    story: Mapped["Story"] = relationship(back_populates="bob_sessions")
    outcomes: Mapped[list["Outcome"]] = relationship(back_populates="bob_session")


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------

class Outcome(Base):
    """Recorded outcome of a story after work is complete."""

    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(
        String, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bob_session_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("bob_sessions.id", ondelete="SET NULL"), nullable=True
    )
    developer_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("developer_profiles.id", ondelete="SET NULL"), nullable=True
    )
    # "pass" | "fail" | "skipped"
    test_result: Mapped[str | None] = mapped_column(String, nullable=True)
    # "pass" | "fail"
    build_result: Mapped[str | None] = mapped_column(String, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ac_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    story: Mapped["Story"] = relationship(back_populates="outcomes")
    bob_session: Mapped["BobSession | None"] = relationship(back_populates="outcomes")
    developer: Mapped["DeveloperProfile | None"] = relationship(back_populates="outcomes")
    comparisons: Mapped[list["Comparison"]] = relationship(
        back_populates="outcome", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class Comparison(Base):
    """Comparison of original recommendation vs actual outcome."""

    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    recommendation_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outcome_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("outcomes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ── Mode comparison ───────────────────────────────────────────────────────
    # "confirmed" | "exceeded" | "diverged"
    mode_verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    mode_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── Dev match comparison ──────────────────────────────────────────────────
    # "matched"|"overridden"|"stretch_succeeded"|"stretch_failed"|"no_match_recorded"
    dev_match_verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    dev_match_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    recommendation: Mapped["Recommendation"] = relationship(back_populates="comparisons")
    outcome: Mapped["Outcome"] = relationship(back_populates="comparisons")


# ---------------------------------------------------------------------------
# ResolvedTicket (M4a)
# ---------------------------------------------------------------------------

class ResolvedTicket(Base):
    """
    A resolved Jira ticket imported for use as historical evidence.

    Used by historical_evidence_service to find semantically similar tickets
    and extract mode/outcome signals for the mode recommendation engine.
    """

    __tablename__ = "resolved_tickets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    jira_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)  # "Done" | "Won't Fix" | etc.
    labels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # PR URLs discovered from Jira remotelinks / dev-status
    linked_prs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Union of files across all linked PRs (populated in M4b from GitHub)
    files_changed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # "bob_led" | "collaborative" | "human_led" — populated from outcome records or sample data
    mode_used: Mapped[str | None] = mapped_column(String, nullable=True)
    ac_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    was_reverted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "jira" | "sample"
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
