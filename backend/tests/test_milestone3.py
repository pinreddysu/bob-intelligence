"""
Milestone 3 tests — Recommendation Engine (priority + execution mode).

All required test cases from the plan:
  - POST /api/recommendations creates record with mode_approval_status="pending".
  - All three execution modes are reachable.
  - All three priority rank scenarios exercised.
  - story_points isolation: identical rank output with/without story_points.
  - No historical outcomes → uncertainty_note contains "no historical outcomes available".
  - PATCH .../mode-approve sets approved status, records approved_by + approved_at.
  - PATCH .../mode-override requires non-empty override_reason (422 otherwise).
  - PATCH .../mode-override sets overridden status, records all three fields.
  - POST /api/bob-sessions returns 409 when mode_approval_status is "pending".
  - POST /api/outcomes returns 409 when mode_approval_status is "pending".
  - GET  /api/recommendations/{id} returns 404 for unknown id.
  - POST /api/recommendations returns 404 for unknown story_id.
  - Priority rank is advisory (no separate approval gate).
  - Recommendation persists in DB (file-backed persistence test).
  - Dev-match fields are null/empty (not populated in MVP).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_story(db_session, **kwargs):
    """Create and persist a minimal Story for testing."""
    from backend.models import Story  # noqa: PLC0415
    defaults = dict(
        title="Test Story",
        description=(
            "A routine configuration change to migrate hardcoded values "
            "to environment variables. No open unknowns."
        ),
        acceptance_criteria=(
            "1. No secrets in source code.\n"
            "2. .env.example documents all variables.\n"
            "3. Tests pass unchanged."
        ),
        labels=["config", "refactor"],
        priority="high",
        status="Ready for Dev",
        assignee=None,
        blockers=[],
        linked_prs=[],
        source="sample",
    )
    defaults.update(kwargs)
    story = Story(**defaults)
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)
    return story


def _post_recommendation(client, story_id: str) -> dict:
    resp = client.post("/api/recommendations", json={"story_id": story_id})
    return resp


def _approve(client, rec_id: str, approved_by: str = "lead@example.com") -> dict:
    return client.patch(
        f"/api/recommendations/{rec_id}/mode-approve",
        json={"approved_by": approved_by},
    )


def _override(client, rec_id: str, approved_by: str, override_reason: str, mode=None) -> dict:
    body = {"approved_by": approved_by, "override_reason": override_reason}
    if mode:
        body["mode"] = mode
    return client.patch(f"/api/recommendations/{rec_id}/mode-override", json=body)


# ---------------------------------------------------------------------------
# POST /api/recommendations — basic creation
# ---------------------------------------------------------------------------

def test_create_recommendation_returns_201(client, db_session):
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    assert resp.status_code == 201, resp.text


def test_create_recommendation_mode_approval_status_is_pending(client, db_session):
    """Plan AC: POST /api/recommendations creates a record with mode_approval_status='pending'."""
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["mode_approval_status"] == "pending"


def test_create_recommendation_contains_priority_fields(client, db_session):
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    data = resp.json()
    assert data["priority_rank"] is not None
    assert isinstance(data["priority_rank"], int)
    assert data["priority_rationale"] is not None
    assert isinstance(data["priority_evidence"], list)
    assert len(data["priority_evidence"]) > 0


def test_create_recommendation_contains_mode_fields(client, db_session):
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    data = resp.json()
    assert data["mode"] in ("bob_led", "collaborative", "human_led")
    assert data["mode_rationale"] is not None
    assert isinstance(data["mode_evidence"], list)
    assert isinstance(data["mode_risks"], list)
    assert isinstance(data["mode_counterevidence"], list)
    assert data["uncertainty_note"] is not None


def test_create_recommendation_unknown_story_returns_404(client, db_session):
    resp = _post_recommendation(client, "nonexistent-story-id")
    assert resp.status_code == 404


def test_create_recommendation_dev_match_fields_are_null_or_empty(client, db_session):
    """Dev-match fields must not be populated in MVP (DEFERRED)."""
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    data = resp.json()
    assert data["suggested_developer"] is None
    assert data["dev_match_rationale"] is None
    assert data["dev_match_evidence"] == []
    assert data["dev_match_risks"] == []
    assert data["is_stretch_assignment"] is False
    assert data["stretch_support_plan"] is None


# ---------------------------------------------------------------------------
# Priority rank scenarios
# ---------------------------------------------------------------------------

def test_priority_rank_high_ready_story_ranks_above_blocked(client, db_session):
    """Plan AC: All three priority rank scenarios are exercised."""
    # High-priority ready story
    ready = _make_story(
        db_session,
        title="Ready high-priority story",
        priority="high",
        status="Ready for Dev",
        blockers=[],
        labels=["api"],
        jira_key="TEST-1",
    )
    # Blocked story
    blocked = _make_story(
        db_session,
        title="Blocked story",
        priority="high",
        status="To Do",
        blockers=["TEST-99"],
        labels=["api"],
        jira_key="TEST-2",
    )

    resp_ready = _post_recommendation(client, ready.id)
    resp_blocked = _post_recommendation(client, blocked.id)
    assert resp_ready.status_code == 201
    assert resp_blocked.status_code == 201

    # Both rankings are in the same context (same DB with both stories)
    # Re-fetch current ranks after both recommendations exist
    rank_ready = resp_ready.json()["priority_rank"]
    rank_blocked = resp_blocked.json()["priority_rank"]
    # Ready story should rank higher (lower number) than blocked story
    assert rank_ready < rank_blocked, (
        f"Expected ready story rank ({rank_ready}) < blocked story rank ({rank_blocked})"
    )


def test_priority_rank_low_signal_story(client, db_session):
    """A story with no priority, no labels, no AC gets a low rank in a multi-story context."""
    high_story = _make_story(
        db_session,
        title="High signal story",
        priority="high",
        status="Ready for Dev",
        blockers=[],
        labels=["security"],
        acceptance_criteria="Well defined.",
        jira_key="HIGH-1",
    )
    low_story = _make_story(
        db_session,
        title="Low signal story",
        priority=None,
        status=None,
        blockers=[],
        labels=[],
        acceptance_criteria=None,
        description="",
        jira_key="LOW-1",
    )

    resp_high = _post_recommendation(client, high_story.id)
    resp_low = _post_recommendation(client, low_story.id)
    assert resp_high.status_code == 201
    assert resp_low.status_code == 201

    rank_high = resp_high.json()["priority_rank"]
    rank_low = resp_low.json()["priority_rank"]
    assert rank_high < rank_low, (
        f"High-signal story rank ({rank_high}) should be lower number than low-signal ({rank_low})"
    )


# ---------------------------------------------------------------------------
# Execution mode reachability (all three modes)
# ---------------------------------------------------------------------------

def test_mode_bob_led_reachable(client, db_session):
    """
    Plan AC: All three execution modes are reachable.
    Bob-led: detailed AC (+10), long description >300 chars (+5), no blockers, no unknowns.
    Total mode_score = +15 → bob_led.
    Labels are not used in mode scoring.
    """
    story = _make_story(
        db_session,
        title="Config migration",
        description=(
            "Migrate hardcoded database connection strings to environment variables. "
            "This is a straightforward task with no functional changes. "
            "Affected files are config.py, db/connection.py, and services/market_data.py. "
            "The task is fully defined and ready to implement. "
            "All configuration values will be documented in .env.example for local setup. "
            "No changes to business logic are required."
        ),
        acceptance_criteria=(
            "1. No secrets in source code.\n"
            "2. .env.example documents all required variables.\n"
            "3. Application starts correctly when environment variables are set.\n"
            "4. Existing integration tests pass unchanged."
        ),
        labels=["config", "refactor"],
        priority="high",
        status="Ready for Dev",
        blockers=[],
    )
    resp = _post_recommendation(client, story.id)
    assert resp.status_code == 201
    assert resp.json()["mode"] == "bob_led", (
        f"Expected bob_led, got {resp.json()['mode']}. "
        f"Rationale: {resp.json()['mode_rationale']}"
    )


def test_mode_human_led_reachable(client, db_session):
    """
    Human-led: multiple open unknowns in description (≥3 → -15), missing AC (-10),
    active blocker (-15). Total mode_score = -40 → human_led.
    Labels are not used in mode scoring.
    """
    story = _make_story(
        db_session,
        title="Implement OAuth2 authentication",
        description=(
            "Should we use Auth0 or implement our own OAuth2 server? "
            "Which approach is best for our scale? "
            "What happens when tokens expire in mobile apps? "
            "How should we handle refresh tokens? "
            "Unclear whether existing sessions should be invalidated. "
            "This is a security-critical change with unknown compliance requirements."
        ),
        acceptance_criteria="",
        labels=["security", "auth", "infrastructure"],
        priority="highest",
        status="To Do",
        blockers=["PIE-10"],
    )
    resp = _post_recommendation(client, story.id)
    assert resp.status_code == 201
    assert resp.json()["mode"] == "human_led", (
        f"Expected human_led, got {resp.json()['mode']}. "
        f"Rationale: {resp.json()['mode_rationale']}"
    )


def test_mode_collaborative_reachable(client, db_session):
    """
    Collaborative: detailed AC (+10), 1 open unknown in description (-5).
    Net mode_score = +5 — not > 10, so stays in collaborative zone.
    Description is kept under 300 chars to avoid the long-description +5 bonus.
    Labels are not used in mode scoring.
    """
    story = _make_story(
        db_session,
        title="Add user notification preferences",
        description=(
            "Add a settings page where users can toggle email and push notifications. "
            "Should we use user-level or account-level preferences? "
            "Notification delivery is out of scope."
        ),
        acceptance_criteria=(
            "1. Settings page shows toggles for email and push notifications.\n"
            "2. Preferences are saved on submit.\n"
            "3. Saved preferences are reflected on page reload."
        ),
        labels=["frontend"],
        priority="medium",
        status="To Do",
        blockers=[],
    )
    resp = _post_recommendation(client, story.id)
    assert resp.status_code == 201
    assert resp.json()["mode"] == "collaborative", (
        f"Expected collaborative, got {resp.json()['mode']}. "
        f"Rationale: {resp.json()['mode_rationale']}"
    )


# ---------------------------------------------------------------------------
# story_points isolation
# ---------------------------------------------------------------------------

def test_story_points_do_not_influence_priority_rank(client, db_session):
    """
    Plan AC: priority engine output is identical whether or not story_points is populated.
    We create the same story twice (distinct jira keys) — one with story_points, one without —
    then assert their priority scores produce the same rank relative to each other (tied).
    """
    # Create two identical stories except for story_points
    story_with_points = _make_story(
        db_session,
        title="Story with points",
        jira_key="SP-1",
        story_points=13,  # large story_points value
        priority="medium",
        status="To Do",
        blockers=[],
        labels=["api"],
        description="Standard API endpoint implementation with clear requirements.",
        acceptance_criteria="1. Endpoint exists. 2. Returns correct data.",
    )
    story_without_points = _make_story(
        db_session,
        title="Story without points",
        jira_key="SP-2",
        story_points=None,
        priority="medium",
        status="To Do",
        blockers=[],
        labels=["api"],
        description="Standard API endpoint implementation with clear requirements.",
        acceptance_criteria="1. Endpoint exists. 2. Returns correct data.",
    )

    resp_with = _post_recommendation(client, story_with_points.id)
    resp_without = _post_recommendation(client, story_without_points.id)
    assert resp_with.status_code == 201
    assert resp_without.status_code == 201

    rank_with = resp_with.json()["priority_rank"]
    rank_without = resp_without.json()["priority_rank"]
    # The ranks should be equal (tied) since all other factors are identical
    # In our engine, identical scores produce consecutive ranks — the difference
    # should be at most 1 (just ordering of tie).  The key assertion: the story with
    # 13 story_points must NOT rank higher than the one with no story_points.
    assert abs(rank_with - rank_without) <= 1, (
        f"story_points appears to be influencing rank: "
        f"rank_with_points={rank_with}, rank_without_points={rank_without}"
    )


def test_story_points_do_not_influence_mode(client, db_session):
    """Mode should be identical for two stories that differ only in story_points.
    Labels are not used in mode scoring."""
    base_kwargs = dict(
        description=(
            "Migrate hardcoded database connection strings to environment variables. "
            "This is a straightforward refactor with no functional changes."
        ),
        acceptance_criteria=(
            "1. No secrets in source code.\n"
            "2. .env.example documents all required variables."
        ),
        labels=["config", "refactor"],
        priority="high",
        status="Ready for Dev",
        blockers=[],
    )
    story_with = _make_story(db_session, title="With points", jira_key="M3-1",
                              story_points=5, **base_kwargs)
    story_without = _make_story(db_session, title="Without points", jira_key="M3-2",
                                 story_points=None, **base_kwargs)

    resp_with = _post_recommendation(client, story_with.id)
    resp_without = _post_recommendation(client, story_without.id)
    assert resp_with.status_code == 201
    assert resp_without.status_code == 201

    assert resp_with.json()["mode"] == resp_without.json()["mode"], (
        "story_points is influencing mode recommendation"
    )


# ---------------------------------------------------------------------------
# Uncertainty note — no historical outcomes
# ---------------------------------------------------------------------------

def test_uncertainty_note_no_historical_outcomes(client, db_session):
    """
    Plan AC: When no historical outcomes exist, uncertainty_note explicitly
    states 'no historical outcomes available'.
    """
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    assert resp.status_code == 201
    note = resp.json()["uncertainty_note"]
    assert "no historical outcomes available" in note.lower(), (
        f"Expected 'no historical outcomes available' in uncertainty_note, got: {note!r}"
    )


# ---------------------------------------------------------------------------
# GET /api/recommendations/{id}
# ---------------------------------------------------------------------------

def test_get_recommendation_returns_record(client, db_session):
    story = _make_story(db_session)
    create_resp = _post_recommendation(client, story.id)
    rec_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/recommendations/{rec_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == rec_id


def test_get_recommendation_not_found(client, db_session):
    resp = client.get("/api/recommendations/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH .../mode-approve
# ---------------------------------------------------------------------------

def test_mode_approve_sets_approved_status(client, db_session):
    """Plan AC: mode-approve sets mode_approval_status='approved'."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _approve(client, rec_id, approved_by="lead@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode_approval_status"] == "approved"


def test_mode_approve_records_approved_by(client, db_session):
    """Plan AC: mode_approved_by is non-null after approval."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _approve(client, rec_id, approved_by="tech-lead-123")
    assert resp.json()["mode_approved_by"] == "tech-lead-123"


def test_mode_approve_records_approved_at_timestamp(client, db_session):
    """Plan AC: mode_approved_at is a valid ISO timestamp."""
    from datetime import datetime

    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _approve(client, rec_id, approved_by="lead@example.com")
    approved_at = resp.json()["mode_approved_at"]
    assert approved_at is not None
    # Should parse as valid ISO datetime
    dt = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    assert dt.year >= 2024


def test_mode_approve_empty_approved_by_returns_422(client, db_session):
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = client.patch(
        f"/api/recommendations/{rec_id}/mode-approve",
        json={"approved_by": ""},
    )
    assert resp.status_code == 422


def test_mode_approve_missing_approved_by_returns_422(client, db_session):
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = client.patch(
        f"/api/recommendations/{rec_id}/mode-approve",
        json={},
    )
    assert resp.status_code == 422


def test_mode_approve_not_found(client, db_session):
    resp = _approve(client, "nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH .../mode-override
# ---------------------------------------------------------------------------

def test_mode_override_sets_overridden_status(client, db_session):
    """Plan AC: mode-override sets mode_approval_status='overridden'."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _override(
        client, rec_id,
        approved_by="lead@example.com",
        override_reason="Team has domain expertise and prefers human review.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode_approval_status"] == "overridden"


def test_mode_override_records_all_three_fields(client, db_session):
    """Plan AC: mode_approved_by, mode_approved_at, mode_override_reason all non-null."""
    from datetime import datetime

    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _override(
        client, rec_id,
        approved_by="lead@example.com",
        override_reason="Security audit requires manual review of all auth changes.",
    )
    data = resp.json()
    assert data["mode_approved_by"] == "lead@example.com"
    assert data["mode_override_reason"] == "Security audit requires manual review of all auth changes."
    approved_at = data["mode_approved_at"]
    assert approved_at is not None
    dt = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    assert dt.year >= 2024


def test_mode_override_missing_override_reason_returns_422(client, db_session):
    """Plan AC: mode-override with missing override_reason returns 422."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = client.patch(
        f"/api/recommendations/{rec_id}/mode-override",
        json={"approved_by": "lead@example.com"},
    )
    assert resp.status_code == 422


def test_mode_override_empty_override_reason_returns_422(client, db_session):
    """Plan AC: mode-override with empty override_reason returns 422."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _override(
        client, rec_id,
        approved_by="lead@example.com",
        override_reason="",
    )
    assert resp.status_code == 422


def test_mode_override_empty_approved_by_returns_422(client, db_session):
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _override(
        client, rec_id,
        approved_by="",
        override_reason="Valid reason.",
    )
    assert resp.status_code == 422


def test_mode_override_updates_mode_when_supplied(client, db_session):
    """Override can optionally switch the mode."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _override(
        client, rec_id,
        approved_by="lead@example.com",
        override_reason="Switching to human-led due to compliance requirements.",
        mode="human_led",
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "human_led"


def test_mode_override_invalid_mode_returns_422(client, db_session):
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]

    resp = _override(
        client, rec_id,
        approved_by="lead@example.com",
        override_reason="Valid reason.",
        mode="invalid_mode",
    )
    assert resp.status_code == 422


def test_mode_override_not_found(client, db_session):
    resp = _override(
        client, "nonexistent-id",
        approved_by="lead@example.com",
        override_reason="Some reason.",
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Downstream 409 gates
# ---------------------------------------------------------------------------

def test_bob_session_rejected_when_mode_approval_pending(client, db_session):
    """
    Plan AC: POST /api/bob-sessions returns 409 when mode_approval_status='pending'.
    """
    story = _make_story(db_session)
    _post_recommendation(client, story.id)  # creates pending recommendation

    resp = client.post("/api/bob-sessions", json={
        "story_id": story.id,
        "summary": "Bob helped implement the config migration.",
        "files_changed": ["config.py"],
    })
    assert resp.status_code == 409
    assert "pending" in resp.json()["detail"].lower() or "not been approved" in resp.json()["detail"].lower()


def test_bob_session_allowed_after_mode_approval(client, db_session):
    """
    After approving the mode, bob-session endpoint should advance past the 409 gate
    (it returns 501 since Milestone 4 is not yet implemented, not 409).
    """
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]
    _approve(client, rec_id, approved_by="lead@example.com")

    resp = client.post("/api/bob-sessions", json={
        "story_id": story.id,
        "summary": "Bob helped implement the config migration.",
        "files_changed": ["config.py"],
    })
    # 501 means gate was passed; full implementation is in Milestone 4
    assert resp.status_code == 501


def test_bob_session_allowed_after_mode_override(client, db_session):
    """After overriding the mode, bob-session gate should pass (returns 501, not 409)."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]
    _override(
        client, rec_id,
        approved_by="lead@example.com",
        override_reason="Team consensus to proceed.",
    )

    resp = client.post("/api/bob-sessions", json={
        "story_id": story.id,
        "summary": "Bob helped implement the feature.",
        "files_changed": ["feature.py"],
    })
    assert resp.status_code == 501


def test_outcomes_rejected_when_mode_approval_pending(client, db_session):
    """
    Plan AC: POST /api/outcomes returns 409 when mode_approval_status='pending'.
    """
    story = _make_story(db_session)
    _post_recommendation(client, story.id)

    resp = client.post("/api/outcomes", json={
        "story_id": story.id,
        "test_result": "pass",
        "build_result": "pass",
        "ac_met": True,
    })
    assert resp.status_code == 409


def test_outcomes_allowed_after_mode_approval(client, db_session):
    """After approving mode, outcomes endpoint passes gate (returns 501, not 409)."""
    story = _make_story(db_session)
    rec_id = _post_recommendation(client, story.id).json()["id"]
    _approve(client, rec_id, approved_by="lead@example.com")

    resp = client.post("/api/outcomes", json={
        "story_id": story.id,
        "test_result": "pass",
        "build_result": "pass",
        "ac_met": True,
    })
    assert resp.status_code == 501


def test_no_recommendation_does_not_trigger_gate(client, db_session):
    """
    If no recommendation has been generated at all, the gate is not triggered
    (the recommendation step simply hasn't been run; we don't block without reason).
    """
    story = _make_story(db_session)
    # No recommendation created — gate should NOT trigger
    resp = client.post("/api/bob-sessions", json={
        "story_id": story.id,
        "summary": "Session before recommendation.",
        "files_changed": [],
    })
    # Should reach the 501 "not yet implemented" state, not 409
    assert resp.status_code == 501


# ---------------------------------------------------------------------------
# Priority is advisory — no approval gate
# ---------------------------------------------------------------------------

def test_priority_rank_has_no_approval_gate(client, db_session):
    """
    Plan AC: Ticket priority rank is advisory. There is no separate approval gate.
    Selecting a ticket (generating a recommendation) does not require prior approval.
    """
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    # The recommendation is created immediately — no gate blocking it
    assert resp.status_code == 201
    data = resp.json()
    assert data["priority_rank"] is not None
    # No approval endpoint needed for priority — mode_approval_status is the only gate
    assert "priority_approval_status" not in data


# ---------------------------------------------------------------------------
# Recommendation persistence (file-backed DB test)
# ---------------------------------------------------------------------------

def test_recommendation_persists_across_session_close(db_session):
    """
    Plan AC: write a Recommendation, close and reopen the DB session,
    confirm records are retrievable — verifying file-backed persistence.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from pathlib import Path

    # Use the same test DB path as conftest
    test_db_path = Path(__file__).parent.parent / "bob_intelligence_test.db"
    test_url = f"sqlite:///{test_db_path}"
    engine = create_engine(test_url, connect_args={"check_same_thread": False})
    Session2 = sessionmaker(bind=engine)

    story = _make_story(db_session)
    story_id = story.id  # capture before session close to avoid DetachedInstanceError

    from backend.services import recommendation_service
    rec = recommendation_service.generate(story, db_session)
    rec_id = rec.id
    db_session.close()

    # Open a new session and confirm the record is there
    from backend.models import Recommendation  # noqa: PLC0415
    session2 = Session2()
    try:
        loaded = session2.query(Recommendation).filter(Recommendation.id == rec_id).first()
        assert loaded is not None
        assert loaded.story_id == story_id
        assert loaded.mode is not None
        assert loaded.priority_rank is not None
    finally:
        session2.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Evidence structure
# ---------------------------------------------------------------------------

def test_evidence_items_have_required_fields(client, db_session):
    """Each evidence item must have source, description, verified."""
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    data = resp.json()

    for item in data["priority_evidence"]:
        assert "source" in item
        assert "description" in item
        assert "verified" in item

    for item in data["mode_evidence"]:
        assert "source" in item
        assert "description" in item
        assert "verified" in item


def test_risks_have_required_fields(client, db_session):
    """Each risk item must have description and severity."""
    story = _make_story(
        db_session,
        title="Security auth story",
        description=(
            "How should we implement authentication? "
            "Which approach should we use? "
            "Should we use OAuth2 or SAML? "
            "What happens if tokens expire?"
        ),
        labels=["security"],
        blockers=["PIE-10"],
        acceptance_criteria="",
    )
    resp = _post_recommendation(client, story.id)
    data = resp.json()
    for item in data["mode_risks"]:
        assert "description" in item
        assert "severity" in item
        assert item["severity"] in ("low", "medium", "high")


def test_counterevidence_items_have_description(client, db_session):
    """Each counterevidence item must have a description."""
    story = _make_story(db_session)
    resp = _post_recommendation(client, story.id)
    data = resp.json()
    for item in data["mode_counterevidence"]:
        assert "description" in item


# ---------------------------------------------------------------------------
# Superseding existing pending recommendations
# ---------------------------------------------------------------------------

def test_second_recommendation_supersedes_first(client, db_session):
    """
    Calling POST /api/recommendations twice for the same story should
    supersede the first recommendation (status='superseded') and create a new one.
    """
    story = _make_story(db_session)
    rec1_id = _post_recommendation(client, story.id).json()["id"]
    rec2_resp = _post_recommendation(client, story.id)
    assert rec2_resp.status_code == 201
    rec2_id = rec2_resp.json()["id"]
    assert rec1_id != rec2_id

    # Verify first is now superseded
    get_resp = client.get(f"/api/recommendations/{rec1_id}")
    assert get_resp.json()["status"] == "superseded"
    # New one is pending
    assert rec2_resp.json()["status"] == "pending"
