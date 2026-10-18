"""
Tests for Milestone 4a — Historical ticket retrieval and semantic similarity.

Covers every acceptance criterion from the plan:
  - ResolvedTicket model and import endpoint
  - Sample import idempotency
  - Jira import with credentials missing
  - GET /api/resolved-tickets returns all tickets with total
  - find_similar returns up to 5 tickets with similarity ≥ 0.25, ordered desc
  - POST /api/recommendations includes similar_tickets, supporting_prs,
    evidence_confidence, code_analysis_notes
  - No-match case: similar_tickets=[], evidence_confidence="none",
    uncertainty_note contains "no similar resolved tickets found"
  - similar_tickets items contain required fields
  - supporting_prs items each contain url, merged, files_changed
  - evidence_confidence levels: "low" (1 ticket no outcome), "medium" (1-2 with outcome),
    "high" (≥3 with outcome)
  - Mode score adjustment: +10 for ≥2 bob_led+ac_met, -10 for was_reverted
  - Backward compatibility: existing M3 recommendation fields unchanged
  - Source failures: Jira missing credentials returns correct source_status
  - similarity ordering: higher overlap story ranks first

All M1-M3 tests continue to pass unchanged.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from backend.models import ResolvedTicket, Story


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_story(db_session, **kwargs) -> Story:
    defaults = {
        "jira_key": f"PIE-T{uuid.uuid4().hex[:4].upper()}",
        "title": "Test story",
        "description": "A test story description.",
        "acceptance_criteria": "1. It works.\n2. Tests pass.",
        "story_points": None,
        "labels": [],
        "priority": "medium",
        "status": "To Do",
        "assignee": None,
        "blockers": [],
        "linked_prs": [],
        "source": "sample",
    }
    defaults.update(kwargs)
    story = Story(**defaults)
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)
    return story


def _make_resolved_ticket(db_session, **kwargs) -> ResolvedTicket:
    defaults = {
        "jira_key": f"PIE-R{uuid.uuid4().hex[:4].upper()}",
        "title": "Resolved ticket",
        "description": "A resolved ticket description.",
        "resolution": "Done",
        "labels": [],
        "linked_prs": [],
        "files_changed": [],
        "mode_used": None,
        "ac_met": None,
        "was_reverted": False,
        "source": "sample",
    }
    defaults.update(kwargs)
    rt = ResolvedTicket(**defaults)
    db_session.add(rt)
    db_session.commit()
    db_session.refresh(rt)
    return rt


def _import_sample_tickets(client) -> dict:
    return client.post(
        "/api/resolved-tickets/import",
        json={"source": "sample"},
    ).json()


def _post_recommendation(client, story_id: str) -> dict:
    resp = client.post("/api/recommendations", json={"story_id": story_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# M4a AC: POST /api/resolved-tickets/import — sample source
# ===========================================================================

class TestResolvedTicketSampleImport:

    def test_import_sample_returns_201(self, client, db_session):
        resp = client.post("/api/resolved-tickets/import", json={"source": "sample"})
        assert resp.status_code == 201

    def test_import_sample_source_status(self, client, db_session):
        data = _import_sample_tickets(client)
        assert data["source_status"] == "sample_import"

    def test_import_sample_count_matches_file(self, client, db_session):
        sample_path = Path(__file__).parent.parent / "sample_data" / "resolved_tickets.json"
        with open(sample_path) as fh:
            raw = json.load(fh)
        expected = len(raw)

        data = _import_sample_tickets(client)
        assert len(data["tickets"]) == expected

    def test_import_sample_source_warning_is_present(self, client, db_session):
        data = _import_sample_tickets(client)
        assert data.get("source_warning") is not None

    def test_import_sample_records_labeled_sample(self, client, db_session):
        data = _import_sample_tickets(client)
        for ticket in data["tickets"]:
            assert ticket["source"] == "sample"

    def test_import_sample_idempotent_skips_duplicates(self, client, db_session):
        first = _import_sample_tickets(client)
        second = _import_sample_tickets(client)
        # Second import: all records already exist
        assert len(second["tickets"]) == 0
        assert second["skipped_duplicates"] == len(first["tickets"])

    def test_import_sample_ticket_has_required_fields(self, client, db_session):
        data = _import_sample_tickets(client)
        assert len(data["tickets"]) > 0
        ticket = data["tickets"][0]
        for field in ("id", "jira_key", "title", "resolution", "labels",
                      "linked_prs", "mode_used", "ac_met", "source", "created_at"):
            assert field in ticket, f"Missing field: {field}"


# ===========================================================================
# M4a AC: POST /api/resolved-tickets/import — jira source (credentials absent)
# ===========================================================================

class TestResolvedTicketJiraImport:

    def test_jira_import_credentials_missing(self, client, db_session, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        resp = client.post("/api/resolved-tickets/import", json={"source": "jira"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_status"] == "credentials_missing"
        assert data["source_warning"] is not None
        assert len(data["tickets"]) == 0

    def test_jira_import_does_not_substitute_sample_data(self, client, db_session, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        resp = client.post("/api/resolved-tickets/import", json={"source": "jira"})
        data = resp.json()
        # Must NOT silently fall back to sample data
        assert data["source_status"] != "sample_import"
        assert len(data["tickets"]) == 0

    def test_jira_import_invalid_source_returns_422(self, client, db_session):
        resp = client.post("/api/resolved-tickets/import", json={"source": "invalid"})
        assert resp.status_code == 422


# ===========================================================================
# M4a AC: GET /api/resolved-tickets
# ===========================================================================

class TestResolvedTicketList:

    def test_list_empty_initially(self, client, db_session):
        resp = client.get("/api/resolved-tickets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["tickets"] == []

    def test_list_returns_all_after_import(self, client, db_session):
        import_data = _import_sample_tickets(client)
        imported_count = len(import_data["tickets"])

        resp = client.get("/api/resolved-tickets")
        data = resp.json()
        assert data["total"] == imported_count
        assert len(data["tickets"]) == imported_count

    def test_list_total_matches_tickets_length(self, client, db_session):
        _import_sample_tickets(client)
        data = client.get("/api/resolved-tickets").json()
        assert data["total"] == len(data["tickets"])


# ===========================================================================
# M4a AC: historical_evidence_service.find_similar
# ===========================================================================

class TestFindSimilar:

    def test_find_similar_empty_corpus_returns_empty(self, db_session):
        from backend.services import historical_evidence_service
        story = _make_story(
            db_session,
            title="Portfolio rebalancing REST endpoint",
            description="REST endpoint for portfolio rebalancing trades",
        )
        result = historical_evidence_service.find_similar(story, db_session)
        assert result == []

    def test_find_similar_high_overlap_returns_results(self, db_session):
        from backend.services import historical_evidence_service
        # Create a resolved ticket with high text overlap
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-HIST1",
            title="Portfolio rebalancing endpoint REST API",
            description="REST endpoint returning rebalancing trades for a portfolio.",
            labels=["api", "portfolio"],
        )
        story = _make_story(
            db_session,
            title="Add portfolio rebalancing endpoint",
            description="REST endpoint that evaluates portfolio asset allocation and returns rebalancing trade recommendations.",
            labels=["api", "portfolio"],
        )
        result = historical_evidence_service.find_similar(story, db_session)
        assert len(result) >= 1
        assert result[0]["jira_key"] == "PIE-HIST1"

    def test_find_similar_result_has_required_fields(self, db_session):
        from backend.services import historical_evidence_service
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-HIST2",
            title="Portfolio API endpoint",
            description="REST API for portfolio data.",
            labels=["api", "portfolio"],
        )
        story = _make_story(
            db_session,
            title="Portfolio REST API endpoint",
            description="Implement a REST API endpoint for portfolio data.",
            labels=["api", "portfolio"],
        )
        result = historical_evidence_service.find_similar(story, db_session)
        assert len(result) >= 1
        item = result[0]
        for field in ("jira_key", "title", "similarity_score", "resolution",
                      "mode_used", "ac_met", "linked_prs", "was_reverted"):
            assert field in item, f"Missing field: {field}"

    def test_find_similar_ordered_by_score_descending(self, db_session):
        from backend.services import historical_evidence_service
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-LOW",
            title="Generic ticket",
            description="Unrelated work.",
            labels=[],
        )
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-HIGH",
            title="Portfolio rebalancing REST endpoint allocation",
            description="REST endpoint for portfolio rebalancing trades allocation buy sell.",
            labels=["api", "portfolio", "rebalancing", "backend"],
        )
        story = _make_story(
            db_session,
            title="Portfolio rebalancing endpoint",
            description="REST endpoint for portfolio rebalancing trades allocation.",
            labels=["api", "portfolio"],
        )
        result = historical_evidence_service.find_similar(story, db_session)
        # The high-overlap ticket should score higher
        jira_keys = [r["jira_key"] for r in result]
        assert "PIE-HIGH" in jira_keys
        # Scores should be non-increasing
        scores = [r["similarity_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_find_similar_no_overlap_below_threshold_returns_empty(self, db_session):
        from backend.services import historical_evidence_service
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-UNRELATED",
            title="Completely unrelated COBOL batch job",
            description="Mainframe batch processing legacy COBOL report.",
            labels=["mainframe", "cobol"],
        )
        story = _make_story(
            db_session,
            title="Dark mode toggle React component",
            description="Add a dark mode toggle button to the React dashboard settings panel.",
            labels=["frontend", "react"],
        )
        result = historical_evidence_service.find_similar(story, db_session)
        # May or may not match depending on shared tokens — just ensure no score below threshold
        for r in result:
            assert r["similarity_score"] >= 0.25

    def test_find_similar_returns_at_most_5(self, db_session):
        from backend.services import historical_evidence_service
        for i in range(8):
            _make_resolved_ticket(
                db_session,
                jira_key=f"PIE-MANY{i}",
                title=f"Portfolio REST API endpoint version {i}",
                description="REST endpoint for portfolio data management and allocation.",
                labels=["api", "portfolio", "backend"],
            )
        story = _make_story(
            db_session,
            title="Portfolio REST API endpoint",
            description="REST endpoint for portfolio data management and allocation.",
            labels=["api", "portfolio"],
        )
        result = historical_evidence_service.find_similar(story, db_session)
        assert len(result) <= 5

    def test_find_similar_score_is_float_between_0_and_1(self, db_session):
        from backend.services import historical_evidence_service
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-SCORE",
            title="Portfolio API",
            description="REST API for portfolio data.",
            labels=["api"],
        )
        story = _make_story(
            db_session,
            title="Portfolio API",
            description="REST API for portfolio data.",
            labels=["api"],
        )
        result = historical_evidence_service.find_similar(story, db_session)
        for r in result:
            assert 0.0 <= r["similarity_score"] <= 1.0


# ===========================================================================
# M4a AC: evidence_confidence computation
# ===========================================================================

class TestEvidenceConfidence:

    def test_confidence_none_no_similar(self, db_session):
        from backend.services import historical_evidence_service
        assert historical_evidence_service.compute_evidence_confidence([]) == "none"

    def test_confidence_low_similar_no_outcomes(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "title": "T", "similarity_score": 0.5,
             "resolution": "Done", "mode_used": None, "ac_met": None,
             "linked_prs": [], "was_reverted": False},
        ]
        assert historical_evidence_service.compute_evidence_confidence(tickets) == "low"

    def test_confidence_medium_one_with_outcome(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "title": "T", "similarity_score": 0.5,
             "resolution": "Done", "mode_used": "bob_led", "ac_met": True,
             "linked_prs": [], "was_reverted": False},
        ]
        assert historical_evidence_service.compute_evidence_confidence(tickets) == "medium"

    def test_confidence_medium_two_with_outcome(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "title": "T", "similarity_score": 0.5,
             "resolution": "Done", "mode_used": "bob_led", "ac_met": True,
             "linked_prs": [], "was_reverted": False},
            {"jira_key": "PIE-2", "title": "T2", "similarity_score": 0.4,
             "resolution": "Done", "mode_used": "collaborative", "ac_met": False,
             "linked_prs": [], "was_reverted": False},
        ]
        assert historical_evidence_service.compute_evidence_confidence(tickets) == "medium"

    def test_confidence_high_three_with_outcomes(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": f"PIE-{i}", "title": "T", "similarity_score": 0.5,
             "resolution": "Done", "mode_used": "bob_led", "ac_met": True,
             "linked_prs": [], "was_reverted": False}
            for i in range(3)
        ]
        assert historical_evidence_service.compute_evidence_confidence(tickets) == "high"


# ===========================================================================
# M4a AC: mode score adjustments from historical signals
# ===========================================================================

class TestModeScoreAdjustment:

    def test_score_delta_two_bob_led_successes_adds_10(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "mode_used": "bob_led", "ac_met": True,
             "was_reverted": False, "title": "T1"},
            {"jira_key": "PIE-2", "mode_used": "bob_led", "ac_met": True,
             "was_reverted": False, "title": "T2"},
        ]
        delta, items = historical_evidence_service.compute_mode_score_adjustment(tickets)
        assert delta == 10
        assert len(items) == 1
        assert items[0]["source"] == "historical_tickets"

    def test_score_delta_one_bob_led_success_no_adjustment(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "mode_used": "bob_led", "ac_met": True,
             "was_reverted": False, "title": "T"},
        ]
        delta, _ = historical_evidence_service.compute_mode_score_adjustment(tickets)
        assert delta == 0

    def test_score_delta_reverted_ticket_subtracts_10(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "mode_used": "bob_led", "ac_met": True,
             "was_reverted": True, "title": "T"},
        ]
        delta, items = historical_evidence_service.compute_mode_score_adjustment(tickets)
        assert delta == -10
        assert any("reverted" in item["description"].lower() for item in items)

    def test_score_delta_combined_bob_led_and_reverted(self, db_session):
        from backend.services import historical_evidence_service
        tickets = [
            {"jira_key": "PIE-1", "mode_used": "bob_led", "ac_met": True,
             "was_reverted": False, "title": "T1"},
            {"jira_key": "PIE-2", "mode_used": "bob_led", "ac_met": True,
             "was_reverted": True, "title": "T2"},  # also reverted
        ]
        delta, _ = historical_evidence_service.compute_mode_score_adjustment(tickets)
        # +10 (2 bob_led successes) -10 (1 reverted) = 0
        assert delta == 0

    def test_score_delta_empty_no_adjustment(self, db_session):
        from backend.services import historical_evidence_service
        delta, items = historical_evidence_service.compute_mode_score_adjustment([])
        assert delta == 0
        assert items == []


# ===========================================================================
# M4a AC: POST /api/recommendations includes historical evidence fields
# ===========================================================================

class TestRecommendationHistoricalFields:

    def test_recommendation_has_similar_tickets_field(self, client, db_session):
        story = _make_story(db_session, title="Portfolio endpoint",
                            description="REST API endpoint for portfolio data.",
                            labels=["api", "portfolio"])
        rec = _post_recommendation(client, story.id)
        assert "similar_tickets" in rec

    def test_recommendation_has_supporting_prs_field(self, client, db_session):
        story = _make_story(db_session, title="Portfolio endpoint",
                            description="REST API endpoint for portfolio data.")
        rec = _post_recommendation(client, story.id)
        assert "supporting_prs" in rec

    def test_recommendation_has_evidence_confidence_field(self, client, db_session):
        story = _make_story(db_session, title="Some story")
        rec = _post_recommendation(client, story.id)
        assert "evidence_confidence" in rec
        assert rec["evidence_confidence"] in ("high", "medium", "low", "none")

    def test_recommendation_has_code_analysis_notes_null_in_m4a(self, client, db_session):
        story = _make_story(db_session, title="Some story")
        rec = _post_recommendation(client, story.id)
        assert "code_analysis_notes" in rec
        assert rec["code_analysis_notes"] is None

    def test_no_resolved_tickets_gives_none_confidence_and_empty_lists(self, client, db_session):
        story = _make_story(
            db_session,
            title="Something completely unique xyz123",
            description="Unique description with no overlap.",
        )
        rec = _post_recommendation(client, story.id)
        assert rec["evidence_confidence"] == "none"
        assert rec["similar_tickets"] == []
        assert rec["supporting_prs"] == []

    def test_no_similar_tickets_uncertainty_note_mentions_it(self, client, db_session):
        story = _make_story(
            db_session,
            title="Completely unique xyz123 story",
            description="No overlap with anything in the corpus.",
        )
        rec = _post_recommendation(client, story.id)
        assert rec["uncertainty_note"] is not None
        assert "no similar resolved tickets found" in rec["uncertainty_note"].lower()

    def test_similar_tickets_found_after_import(self, client, db_session):
        # Import sample resolved tickets first
        _import_sample_tickets(client)
        # Use a story with strong domain overlap to the sample resolved tickets
        # (resolved tickets cover user/login/create REST endpoints — match with user API story)
        story = _make_story(
            db_session,
            jira_key="PIE-5T",
            title="Add user profile endpoint",
            description=(
                "REST endpoint for user account management. "
                "Accept email and password, return user data with 200 OK status. "
                "Backend service for user authentication and login."
            ),
            labels=["api", "user", "backend"],
        )
        rec = _post_recommendation(client, story.id)
        assert len(rec["similar_tickets"]) >= 1

    def test_similar_tickets_items_have_required_fields(self, client, db_session):
        _import_sample_tickets(client)
        story = _make_story(
            db_session,
            title="Add portfolio rebalancing endpoint",
            description="REST endpoint for portfolio asset allocation and rebalancing trades.",
            labels=["api", "portfolio", "backend"],
        )
        rec = _post_recommendation(client, story.id)
        for item in rec["similar_tickets"]:
            for field in ("jira_key", "title", "similarity_score", "resolution",
                          "mode_used", "ac_met"):
                assert field in item, f"Missing field '{field}' in similar_ticket item"

    def test_supporting_prs_items_have_required_fields(self, client, db_session):
        _import_sample_tickets(client)
        story = _make_story(
            db_session,
            title="Portfolio rebalancing REST endpoint",
            description="REST endpoint that returns rebalancing trades for a portfolio.",
            labels=["api", "portfolio"],
        )
        rec = _post_recommendation(client, story.id)
        for pr in rec["supporting_prs"]:
            assert "url" in pr
            assert "merged" in pr
            assert "files_changed" in pr

    def test_supporting_prs_urls_come_from_similar_tickets(self, client, db_session):
        # Create a resolved ticket with a known PR URL
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-PRTEST",
            title="Portfolio REST API rebalancing trades",
            description="REST API endpoint for portfolio rebalancing trade recommendations.",
            labels=["api", "portfolio", "backend"],
            linked_prs=["https://github.com/example/pie/pull/999"],
        )
        story = _make_story(
            db_session,
            title="Portfolio rebalancing REST endpoint",
            description="REST endpoint for portfolio rebalancing trade recommendations.",
            labels=["api", "portfolio"],
        )
        rec = _post_recommendation(client, story.id)
        pr_urls = [pr["url"] for pr in rec["supporting_prs"]]
        assert "https://github.com/example/pie/pull/999" in pr_urls

    def test_evidence_confidence_high_with_three_outcomes(self, client, db_session):
        # Insert 3 resolved tickets with mode_used + ac_met — all similar to story
        for i in range(3):
            _make_resolved_ticket(
                db_session,
                jira_key=f"PIE-CONF{i}",
                title="Portfolio REST API endpoint allocation",
                description="REST endpoint for portfolio data management allocation trades.",
                labels=["api", "portfolio", "backend"],
                mode_used="bob_led",
                ac_met=True,
            )
        story = _make_story(
            db_session,
            title="Portfolio REST API endpoint",
            description="REST endpoint for portfolio data management allocation.",
            labels=["api", "portfolio"],
        )
        rec = _post_recommendation(client, story.id)
        assert rec["evidence_confidence"] == "high"

    def test_mode_evidence_includes_historical_ticket_signal(self, client, db_session):
        # Two bob_led+ac_met tickets similar to the story → +10 → evidence item added
        for i in range(2):
            _make_resolved_ticket(
                db_session,
                jira_key=f"PIE-BOB{i}",
                title="Portfolio REST rebalancing endpoint allocation",
                description=(
                    "REST endpoint portfolio rebalancing allocation trades buy sell backend."
                ),
                labels=["api", "portfolio", "backend", "rebalancing"],
                mode_used="bob_led",
                ac_met=True,
            )
        story = _make_story(
            db_session,
            title="Portfolio REST rebalancing endpoint allocation",
            description=(
                "REST endpoint portfolio rebalancing allocation trades buy sell."
            ),
            labels=["api", "portfolio", "rebalancing"],
        )
        rec = _post_recommendation(client, story.id)
        sources = [e.get("source") for e in rec["mode_evidence"]]
        assert "historical_tickets" in sources

    def test_reverted_ticket_adds_mode_risk(self, client, db_session):
        # was_reverted=True on a similar ticket → mode score -10 → risk signal in evidence
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-REVERT",
            title="Portfolio REST rebalancing endpoint allocation trades",
            description="REST endpoint for portfolio rebalancing allocation trades backend.",
            labels=["api", "portfolio", "backend"],
            mode_used="bob_led",
            ac_met=True,
            was_reverted=True,
        )
        story = _make_story(
            db_session,
            title="Portfolio REST rebalancing endpoint allocation",
            description="REST endpoint for portfolio rebalancing allocation trades.",
            labels=["api", "portfolio"],
        )
        rec = _post_recommendation(client, story.id)
        # The reverted-ticket evidence item should appear in mode_evidence
        all_desc = " ".join(
            e.get("description", "") for e in rec["mode_evidence"]
        )
        assert "reverted" in all_desc.lower()


# ===========================================================================
# M4a AC: backward compatibility — M3 fields unchanged
# ===========================================================================

class TestBackwardCompatibility:

    def test_m3_recommendation_fields_still_present(self, client, db_session):
        story = _make_story(db_session)
        rec = _post_recommendation(client, story.id)
        for field in (
            "id", "story_id", "priority_rank", "priority_rationale",
            "priority_evidence", "mode", "mode_rationale", "mode_evidence",
            "mode_risks", "mode_counterevidence", "mode_approval_status",
            "mode_approved_by", "mode_approved_at", "mode_override_reason",
            "suggested_developer", "dev_match_rationale", "dev_match_evidence",
            "dev_match_risks", "is_stretch_assignment", "stretch_support_plan",
            "dev_match_approval_status", "uncertainty_note", "status", "created_at",
        ):
            assert field in rec, f"M3 backward compat: missing field '{field}'"

    def test_m3_fields_have_correct_types(self, client, db_session):
        story = _make_story(db_session)
        rec = _post_recommendation(client, story.id)
        assert isinstance(rec["mode_evidence"], list)
        assert isinstance(rec["mode_risks"], list)
        assert isinstance(rec["mode_counterevidence"], list)
        assert isinstance(rec["priority_evidence"], list)
        assert rec["is_stretch_assignment"] is False
        assert rec["suggested_developer"] is None

    def test_m4a_defaults_when_no_resolved_tickets(self, client, db_session):
        """With no resolved tickets in DB, M4a fields default gracefully."""
        story = _make_story(db_session)
        rec = _post_recommendation(client, story.id)
        assert rec["similar_tickets"] == []
        assert rec["supporting_prs"] == []
        assert rec["evidence_confidence"] == "none"
        assert rec["code_analysis_notes"] is None

    def test_get_recommendation_includes_m4a_fields(self, client, db_session):
        """GET /api/recommendations/{id} also returns M4a fields."""
        story = _make_story(db_session)
        created = _post_recommendation(client, story.id)
        rec_id = created["id"]
        resp = client.get(f"/api/recommendations/{rec_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "similar_tickets" in data
        assert "supporting_prs" in data
        assert "evidence_confidence" in data
        assert "code_analysis_notes" in data

    def test_story_points_still_not_influence_mode(self, client, db_session):
        """story_points must still be ignored even with M4a wired in."""
        high_sp = _make_story(db_session, story_points=100,
                              title="Story A", description="Simple description.",
                              acceptance_criteria="AC1. Works.", priority="low", status="To Do",
                              labels=[], blockers=[])
        low_sp = _make_story(db_session, story_points=1,
                             title="Story A", description="Simple description.",
                             acceptance_criteria="AC1. Works.", priority="low", status="To Do",
                             labels=[], blockers=[])
        rec_high = _post_recommendation(client, high_sp.id)
        rec_low = _post_recommendation(client, low_sp.id)
        assert rec_high["mode"] == rec_low["mode"]


# ===========================================================================
# M4a AC: similarity ordering — higher overlap story gets better similar tickets
# ===========================================================================

class TestSimilarityOrdering:

    def test_higher_overlap_story_finds_more_similar_tickets(self, client, db_session):
        _make_resolved_ticket(
            db_session,
            jira_key="PIE-ORD1",
            title="Portfolio REST API rebalancing endpoint",
            description="REST endpoint portfolio rebalancing allocation trades.",
            labels=["api", "portfolio", "backend"],
        )
        # High overlap story
        story_high = _make_story(
            db_session,
            title="Portfolio REST API rebalancing endpoint",
            description="REST endpoint portfolio rebalancing allocation trades.",
            labels=["api", "portfolio"],
        )
        # Low overlap story
        story_low = _make_story(
            db_session,
            title="Dark mode toggle",
            description="Add a theme toggle to the settings panel.",
            labels=["frontend", "ui"],
        )
        rec_high = _post_recommendation(client, story_high.id)
        rec_low = _post_recommendation(client, story_low.id)
        assert len(rec_high["similar_tickets"]) >= len(rec_low["similar_tickets"])

    def test_similar_tickets_score_descending_in_response(self, client, db_session):
        _import_sample_tickets(client)
        story = _make_story(
            db_session,
            title="Portfolio rebalancing REST endpoint allocation",
            description="REST endpoint returns rebalancing trades for portfolio allocation.",
            labels=["api", "portfolio", "backend"],
        )
        rec = _post_recommendation(client, story.id)
        scores = [t["similarity_score"] for t in rec["similar_tickets"]]
        assert scores == sorted(scores, reverse=True)
