"""
Tests for priority ranking eligibility — terminal-status filtering.

The plan states: "Prioritizes which open Jira ticket the team should work on
next."  Stories with terminal statuses (Done, Closed, Resolved, etc.) are
complete work and must NOT compete in priority rankings against actionable
stories.

Covers:
  - _STATUS_TERMINAL constant contains the expected terminal statuses.
  - generate() filters Done/Closed/Resolved stories from the ranking pool.
  - An open story always ranks ahead of a story that would be terminal
    (via the integration endpoint — the terminal story is excluded from the pool).
  - The target story itself (the one receiving the recommendation) is always
    included even if its status is terminal, so a recommendation can still be
    generated.
  - Case-insensitive filtering: "done", "DONE", "Done" are all excluded.
  - Whitespace tolerance: " Done " is excluded.
  - Status=None (not set) is treated as open, not terminal.
  - A story whose status is not in the terminal set but also not in the ready/
    active sets is treated as open and included in ranking.
  - story_points isolation is preserved after the filtering change.
"""

from __future__ import annotations

import pytest

from backend.services.recommendation_service import (
    _STATUS_TERMINAL,
    compute_priority_rankings,
)
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helper: create a minimal story mock
# ---------------------------------------------------------------------------

def _story(id_: str, status: str | None = "To Do", priority: str | None = None,
           ac: str | None = None, blockers=None, labels=None, description: str = ""):
    s = MagicMock()
    s.id = id_
    s.status = status
    s.priority = priority
    s.labels = labels or []
    s.acceptance_criteria = ac
    s.blockers = blockers or []
    s.description = description
    return s


# ===========================================================================
# _STATUS_TERMINAL constant
# ===========================================================================

class TestStatusTerminalConstant:
    """_STATUS_TERMINAL must contain exactly the documented terminal statuses."""

    def test_done_is_terminal(self):
        assert "done" in _STATUS_TERMINAL

    def test_closed_is_terminal(self):
        assert "closed" in _STATUS_TERMINAL

    def test_resolved_is_terminal(self):
        assert "resolved" in _STATUS_TERMINAL

    def test_wont_fix_is_terminal(self):
        assert "won't fix" in _STATUS_TERMINAL or "wont fix" in _STATUS_TERMINAL

    def test_cancelled_is_terminal(self):
        assert "cancelled" in _STATUS_TERMINAL or "canceled" in _STATUS_TERMINAL

    def test_rejected_is_terminal(self):
        assert "rejected" in _STATUS_TERMINAL

    def test_duplicate_is_terminal(self):
        assert "duplicate" in _STATUS_TERMINAL

    def test_to_do_is_not_terminal(self):
        assert "to do" not in _STATUS_TERMINAL

    def test_in_progress_is_not_terminal(self):
        assert "in progress" not in _STATUS_TERMINAL

    def test_ready_for_dev_is_not_terminal(self):
        assert "ready for dev" not in _STATUS_TERMINAL

    def test_backlog_is_not_terminal(self):
        assert "backlog" not in _STATUS_TERMINAL


# ===========================================================================
# compute_priority_rankings — called directly with filtered list
# ===========================================================================

class TestRankingWithFilter:
    """When a pre-filtered list is passed, Done stories are absent."""

    def test_done_story_excluded_from_ranking(self):
        open_s = _story("open-1", status="To Do", priority="high")
        done_s = _story("done-1", status="Done", priority="highest")

        # Simulate the filter that generate() now applies
        eligible = [s for s in [open_s, done_s]
                    if (s.status or "").lower().strip() not in _STATUS_TERMINAL]
        result = compute_priority_rankings(eligible)

        assert "done-1" not in result
        assert "open-1" in result

    def test_closed_story_excluded_from_ranking(self):
        open_s = _story("open-1", status="In Progress")
        closed_s = _story("closed-1", status="Closed")

        eligible = [s for s in [open_s, closed_s]
                    if (s.status or "").lower().strip() not in _STATUS_TERMINAL]
        result = compute_priority_rankings(eligible)

        assert "closed-1" not in result
        assert "open-1" in result

    def test_resolved_story_excluded(self):
        open_s = _story("open-1", status="Ready for Dev")
        resolved_s = _story("resolved-1", status="Resolved")

        eligible = [s for s in [open_s, resolved_s]
                    if (s.status or "").lower().strip() not in _STATUS_TERMINAL]
        result = compute_priority_rankings(eligible)

        assert "resolved-1" not in result

    def test_none_status_is_included(self):
        """status=None means unset, not terminal."""
        s = _story("s1", status=None)
        eligible = [s2 for s2 in [s]
                    if (s2.status or "").lower().strip() not in _STATUS_TERMINAL]
        result = compute_priority_rankings(eligible)
        assert "s1" in result

    def test_unknown_non_terminal_status_is_included(self):
        """An arbitrary unknown status is open until proven terminal."""
        s = _story("s1", status="Waiting for Feedback")
        eligible = [s2 for s2 in [s]
                    if (s2.status or "").lower().strip() not in _STATUS_TERMINAL]
        result = compute_priority_rankings(eligible)
        assert "s1" in result

    def test_done_case_insensitive_excluded(self):
        for status in ["done", "DONE", "Done", "dOnE"]:
            s = _story(f"s-{status}", status=status)
            eligible = [s2 for s2 in [s]
                        if (s2.status or "").lower().strip() not in _STATUS_TERMINAL]
            assert len(eligible) == 0, f"Status '{status}' should be terminal"

    def test_done_with_surrounding_whitespace_excluded(self):
        s = _story("s1", status="  Done  ")
        eligible = [s2 for s2 in [s]
                    if (s2.status or "").lower().strip() not in _STATUS_TERMINAL]
        assert len(eligible) == 0

    def test_open_story_rank_unaffected_by_absent_done_stories(self):
        """Rank of an open story must be 1 of N where N counts only open stories."""
        open_a = _story("open-a", status="To Do", priority="high")
        open_b = _story("open-b", status="Ready for Dev", priority="medium")
        done_x = _story("done-x", status="Done", priority="highest")

        eligible = [s for s in [open_a, open_b, done_x]
                    if (s.status or "").lower().strip() not in _STATUS_TERMINAL]
        result = compute_priority_rankings(eligible)

        # Rationale must say "2 stories", not "3 stories"
        _, _, rationale_a = result["open-a"]
        assert "2 stories" in rationale_a

    def test_all_done_stories_produce_empty_ranking(self):
        done_stories = [
            _story(f"d{i}", status="Done") for i in range(3)
        ]
        eligible = [s for s in done_stories
                    if (s.status or "").lower().strip() not in _STATUS_TERMINAL]
        assert len(eligible) == 0
        result = compute_priority_rankings(eligible)
        assert result == {}


# ===========================================================================
# Integration tests — via HTTP endpoint
# ===========================================================================

class TestRankingEligibilityIntegration:
    """End-to-end: terminal-status stories are excluded from the pool used
    to compute priority_rank for an open story."""

    def _make_story(self, db_session, **kwargs):
        from backend.models import Story
        defaults = dict(
            title="Story",
            description="A description.",
            acceptance_criteria="1. Returns 200.\n2. Saves record.",
            labels=[],
            priority="medium",
            status="To Do",
            assignee=None,
            blockers=[],
            linked_prs=[],
            source="sample",
        )
        defaults.update(kwargs)
        s = Story(**defaults)
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    def _post_rec(self, client, story_id):
        resp = client.post("/api/recommendations", json={"story_id": story_id})
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_done_story_not_in_ranking_pool(self, client, db_session):
        """A Done story must not compete with open stories in priority ranking."""
        open_story = self._make_story(db_session, jira_key="OPEN-1",
                                      title="Open story", priority="low")
        done_story = self._make_story(db_session, jira_key="DONE-1",
                                      title="Done story", priority="highest",
                                      status="Done")

        rec = self._post_rec(client, open_story.id)
        # With Done story excluded, open_story is ranked 1 of 1 open stories
        # (the Done story should not make it rank 2 of 2)
        assert rec["priority_rank"] == 1
        assert "1 stories" in rec["priority_rationale"] or "1 story" in rec["priority_rationale"]

    def test_closed_story_not_in_ranking_pool(self, client, db_session):
        open_story = self._make_story(db_session, jira_key="OPEN-2",
                                      title="Open story 2", priority="medium")
        closed_story = self._make_story(db_session, jira_key="CLOSED-1",
                                        title="Closed story", priority="high",
                                        status="Closed")

        rec = self._post_rec(client, open_story.id)
        assert rec["priority_rank"] == 1
        assert "1 stories" in rec["priority_rationale"] or "1 story" in rec["priority_rationale"]

    def test_open_story_ranks_against_only_open_stories(self, client, db_session):
        """With 2 open stories and 1 Done, ranks are 1 and 2, not 1 and 3."""
        high = self._make_story(db_session, jira_key="H-1", title="High",
                                priority="high", status="Ready for Dev")
        low = self._make_story(db_session, jira_key="L-1", title="Low",
                               priority="low", status="To Do")
        done = self._make_story(db_session, jira_key="D-1", title="Done",
                                priority="highest", status="Done")

        rec_high = self._post_rec(client, high.id)
        rec_low = self._post_rec(client, low.id)

        # Both rationales must reference 2 stories (not 3)
        assert "2 stories" in rec_high["priority_rationale"]
        assert "2 stories" in rec_low["priority_rationale"]
        # Ranks must be 1 and 2
        ranks = {rec_high["priority_rank"], rec_low["priority_rank"]}
        assert ranks == {1, 2}

    def test_resolved_story_not_in_ranking_pool(self, client, db_session):
        open_story = self._make_story(db_session, jira_key="OPEN-3",
                                      title="Open 3", priority="medium")
        self._make_story(db_session, jira_key="RES-1", title="Resolved",
                         status="Resolved", priority="highest")

        rec = self._post_rec(client, open_story.id)
        assert rec["priority_rank"] == 1

    def test_story_points_isolation_preserved_after_filter(self, client, db_session):
        """story_points must still not influence rank after the terminal-status change."""
        with_pts = self._make_story(db_session, jira_key="SP-W",
                                    story_points=100, priority="medium",
                                    status="To Do")
        without_pts = self._make_story(db_session, jira_key="SP-X",
                                       story_points=None, priority="medium",
                                       status="To Do")

        rec_w = self._post_rec(client, with_pts.id)
        rec_x = self._post_rec(client, without_pts.id)

        # Ranks must differ by at most 1 (tie-breaking), same as before
        assert abs(rec_w["priority_rank"] - rec_x["priority_rank"]) <= 1

    def test_generating_rec_for_done_story_still_works(self, client, db_session):
        """A Done story can still receive a recommendation; it just competes only
        against other open stories (plus itself, always in the pool)."""
        open_s = self._make_story(db_session, jira_key="OPEN-D", title="Open",
                                  priority="high", status="To Do")
        done_s = self._make_story(db_session, jira_key="DONE-R", title="Done story",
                                  priority="medium", status="Done")

        rec = self._post_rec(client, done_s.id)
        # Recommendation generated successfully
        assert rec["priority_rank"] is not None
        assert rec["mode"] in ("bob_led", "collaborative", "human_led")
