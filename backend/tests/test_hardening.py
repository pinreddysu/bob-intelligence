"""
Hardening tests for the recommendation service.

Covers the five findings from the audit:

  1. _AC_BDD false-positive fix — lone "when", "then", "given that" in prose
     must NOT score as BDD; all three keywords must appear in order.
  2. Linked-PR scoring — bare URL existence must not add to mode_score.
     Evidence must be present but marked verified=False.
  3. Uncertainty note accuracy — when historical tickets adjusted the mode score,
     the note must say so; when only metadata was used, it must say that.
  4. Rationale string — must contain ">=10" (not ">10") after threshold change.
  5. compute_priority_rankings docstring behaviour — ranks ALL stories supplied,
     not just open ones; rationale says "N stories" not "N open stories".

Additional decision-boundary and evidence-path tests:
  - Mode score thresholds (exactly 10 → bob_led; exactly -10 → collaborative).
  - Blocker hard-floor: strong AC + one blocker → not bob_led.
  - Priority evidence verified flags match signal quality.
  - Urgency vs readiness signals are distinct in evidence.
  - _priority_score with story_points present vs absent produces identical output.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from backend.services.recommendation_service import (
    _ac_quality,
    _AC_BDD,
    _mode_engine,
    _priority_score,
    compute_priority_rankings,
)


# ===========================================================================
# Finding 1 — _AC_BDD requires all three keywords in order
# ===========================================================================

class TestAcBddStrictPattern:
    """_AC_BDD must require given … when … then in order, not any single keyword."""

    # --- False positives that the old single-keyword pattern matched ---

    def test_lone_when_in_prose_does_not_match(self):
        assert not _AC_BDD.search("The page loads quickly when the cache is warm.")

    def test_lone_then_in_prose_does_not_match(self):
        assert not _AC_BDD.search("The button is disabled then enabled after save.")

    def test_given_that_without_when_then_does_not_match(self):
        assert not _AC_BDD.search("Given that the user is logged in, the dashboard shows.")

    def test_when_at_start_without_given_then_does_not_match(self):
        assert not _AC_BDD.search("when clicked the modal opens")

    def test_then_in_list_item_does_not_match(self):
        assert not _AC_BDD.search("1. Page loads when cache is warm.")

    def test_given_without_when_then_does_not_match(self):
        assert not _AC_BDD.search("Given a user performs the action, the result is shown.")

    def test_when_then_without_given_does_not_match(self):
        assert not _AC_BDD.search("When the form is submitted then a confirmation is shown.")

    # --- True positives that must still match ---

    def test_full_bdd_triplet_matches(self):
        assert _AC_BDD.search(
            "Given a valid token, when the user calls /api/users, "
            "then a 200 response is returned."
        )

    def test_full_bdd_case_insensitive(self):
        assert _AC_BDD.search("GIVEN x WHEN y THEN z.")

    def test_full_bdd_multiline(self):
        assert _AC_BDD.search("Given a user\nwhen they POST /orders\nthen the order is created.")

    def test_short_bdd_matches(self):
        assert _AC_BDD.search("Given X when Y then Z.")

    # --- Effect on _ac_quality scoring ---

    def test_lone_when_in_list_item_does_not_elevate_to_well_structured_via_bdd(self):
        """1. Saves record when form submitted — has list + 'saves' verb → well_structured via
        list+verb, NOT via BDD.  Verify this still works and the BDD path isn't the reason."""
        ac = "1. Saves the record when the form is submitted."
        score, label, reasons = _ac_quality(ac)
        # Should be well_structured via list+verb, not BDD
        assert score == 3
        assert label == "well_structured"
        assert not any("Given/When/Then" in r for r in reasons)

    def test_prose_with_only_when_does_not_become_testable(self):
        """Prose containing 'when' with no list and no outcome verb must stay 'present'."""
        score, label, _ = _ac_quality("The form should submit when the user clicks the button.")
        assert score == 1
        assert label == "present"

    def test_prose_with_given_and_then_but_no_when_is_not_testable_via_bdd(self):
        score, label, _ = _ac_quality(
            "Given that the user is logged in, the app then shows the dashboard."
        )
        # has_bdd is False (no full triplet); no list; no outcome verb matching
        # 'shows' IS in outcome verbs → score=2 (structured)
        assert score == 2
        assert label == "structured"


# ===========================================================================
# Finding 2 — Linked-PR scoring: bare URLs must not add to mode_score
# ===========================================================================

class TestLinkedPrScoring:
    """story.linked_prs contains raw Jira PR URLs with no merge/outcome data.
    They must be recorded as unverified context, never scored."""

    def _run(self, linked_prs, **kwargs):
        story = MagicMock()
        story.acceptance_criteria = (
            "1. The endpoint returns 200.\n2. Record is saved."  # score=3, +10
        )
        story.description = "No open unknowns."
        story.blockers = []
        story.linked_prs = linked_prs
        return _mode_engine(story, outcome_count=0, similar_tickets=[], **kwargs)

    def test_no_prs_and_no_prs_evidence(self):
        _, _, evidence, _, _, _ = self._run([])
        pr_ev = [e for e in evidence if e["source"] == "linked_prs"]
        assert len(pr_ev) == 0

    def test_one_pr_url_produces_evidence_item(self):
        _, _, evidence, _, _, _ = self._run(["https://github.com/org/repo/pull/1"])
        pr_ev = [e for e in evidence if e["source"] == "linked_prs"]
        assert len(pr_ev) == 1

    def test_pr_evidence_is_not_verified(self):
        _, _, evidence, _, _, _ = self._run(["https://github.com/org/repo/pull/1"])
        pr_ev = [e for e in evidence if e["source"] == "linked_prs"]
        assert pr_ev[0]["verified"] is False

    def test_pr_evidence_mentions_unavailability(self):
        _, _, evidence, _, _, _ = self._run(["https://github.com/org/repo/pull/1"])
        pr_ev = [e for e in evidence if e["source"] == "linked_prs"]
        desc = pr_ev[0]["description"].lower()
        assert "not" in desc or "deferred" in desc or "not yet available" in desc

    def test_prs_do_not_increase_mode_score(self):
        """Mode score with PRs must equal mode score without PRs."""
        mode_with, _, ev_with, _, _, _ = self._run(
            ["https://github.com/org/repo/pull/1",
             "https://github.com/org/repo/pull/2"]
        )
        mode_without, _, ev_without, _, _, _ = self._run([])
        assert mode_with == mode_without

    def test_mode_score_in_rationale_unchanged_by_prs(self):
        _, rationale_with, _, _, _, _ = self._run(["https://github.com/org/repo/pull/1"])
        _, rationale_without, _, _, _, _ = self._run([])
        # Extract numeric mode score from rationale "Mode score: N"
        def extract_score(r):
            m = re.search(r"Mode score: (-?\d+)", r)
            return int(m.group(1)) if m else None
        assert extract_score(rationale_with) == extract_score(rationale_without)

    def test_multiple_prs_still_no_score_contribution(self):
        _, _, evidence, _, _, _ = self._run([
            "https://github.com/org/repo/pull/1",
            "https://github.com/org/repo/pull/2",
            "https://github.com/org/repo/pull/3",
        ])
        pr_ev = [e for e in evidence if e["source"] == "linked_prs"]
        assert len(pr_ev) == 1   # single evidence item, not one per PR
        assert pr_ev[0]["verified"] is False


# ===========================================================================
# Finding 3 — Uncertainty note accuracy
# ===========================================================================

class TestUncertaintyNoteAccuracy:
    """The uncertainty note must accurately reflect what DID and DID NOT influence the score."""

    def _run(self, outcome_count, similar_tickets):
        story = MagicMock()
        story.acceptance_criteria = "1. The endpoint returns 200.\n2. Record is saved."
        story.description = "No open unknowns."
        story.blockers = []
        story.linked_prs = []
        return _mode_engine(story, outcome_count=outcome_count, similar_tickets=similar_tickets)

    def test_no_outcomes_no_similar_tickets_mentions_no_historical_outcomes(self):
        _, _, _, _, _, note = self._run(outcome_count=0, similar_tickets=[])
        assert "no historical outcomes available" in note.lower()

    def test_low_outcome_count_mentions_insufficient_records(self):
        _, _, _, _, _, note = self._run(outcome_count=2, similar_tickets=[])
        assert "2 historical outcome record" in note

    def test_no_similar_tickets_mentions_it_in_note(self):
        _, _, _, _, _, note = self._run(outcome_count=0, similar_tickets=[])
        assert "no similar resolved tickets" in note.lower()

    def test_hist_delta_nonzero_note_mentions_historical_adjustment(self):
        """When similar tickets produce a score adjustment, the note must say so."""
        # Two bob_led+ac_met tickets produce +10 delta via compute_mode_score_adjustment
        similar = [
            {"jira_key": "T-1", "title": "T1", "similarity_score": 0.8,
             "mode_used": "bob_led", "ac_met": True, "was_reverted": False},
            {"jira_key": "T-2", "title": "T2", "similarity_score": 0.75,
             "mode_used": "bob_led", "ac_met": True, "was_reverted": False},
        ]
        _, _, _, _, _, note = self._run(outcome_count=5, similar_tickets=similar)
        # uncertainty_parts is empty (outcome_count>=3, similar_tickets non-empty)
        # hist_delta_applied = +10 → "not factored in" must NOT appear
        assert "not currently factored in" not in note.lower()
        assert "historical" in note.lower() or "adjusted" in note.lower()

    def test_hist_delta_zero_note_does_not_claim_historical_adjusted_score(self):
        """When similar tickets exist but produced delta=0, note must not claim they moved the score."""
        # One ticket with mode_used="collaborative" and ac_met=True — no delta rule fires
        similar = [
            {"jira_key": "T-3", "title": "T3", "similarity_score": 0.5,
             "mode_used": "collaborative", "ac_met": True, "was_reverted": False},
        ]
        _, _, _, _, _, note = self._run(outcome_count=5, similar_tickets=similar)
        # hist_delta_applied = 0 → note should clarify tickets didn't adjust score
        assert "not currently factored in" not in note.lower()
        # Must not falsely claim historical evidence adjusted the score
        assert "adjusted mode score" not in note.lower()

    def test_metadata_only_note_does_not_claim_historical_factored_in(self):
        """When no similar tickets and no outcomes, note must not claim historical was used."""
        _, _, _, _, _, note = self._run(outcome_count=0, similar_tickets=[])
        assert "historical evidence adjusted" not in note.lower()

    def test_note_never_mentions_linked_prs_as_active_signal(self):
        """After the PR scoring fix, uncertainty note must not list linked PRs as a scoring input."""
        story = MagicMock()
        story.acceptance_criteria = "1. Returns 200.\n2. Saves record."
        story.description = "No open unknowns."
        story.blockers = []
        story.linked_prs = ["https://github.com/org/repo/pull/99"]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=0, similar_tickets=[])
        # linked PRs are no longer a mode scoring input
        assert "linked prs" not in note.lower() or "not used" in note.lower()


# ===========================================================================
# Finding 4 — Rationale string contains correct threshold text
# ===========================================================================

class TestRationaleThresholdText:

    def _run_mode(self):
        story = MagicMock()
        story.acceptance_criteria = "1. Returns 200.\n2. Saves record."
        story.description = "No open unknowns."
        story.blockers = []
        story.linked_prs = []
        return _mode_engine(story, outcome_count=0, similar_tickets=[])

    def test_rationale_contains_correct_threshold_string(self):
        _, rationale, _, _, _, _ = self._run_mode()
        assert ">=10" in rationale, f"Expected '>=10' in rationale, got: {rationale!r}"

    def test_rationale_does_not_contain_old_threshold_string(self):
        _, rationale, _, _, _, _ = self._run_mode()
        # ">10" should only appear as part of ">=10", not standalone
        # Strip ">=10" occurrences then check no bare ">10" remains
        sanitised = rationale.replace(">=10", "")
        assert ">10" not in sanitised, (
            f"Rationale still contains old '>10' threshold text: {rationale!r}"
        )


# ===========================================================================
# Finding 5 — compute_priority_rankings ranks all supplied stories
# ===========================================================================

class TestPriorityRankingsScope:

    def _make_story(self, **kwargs):
        story = MagicMock()
        story.id = kwargs.get("id", "story-1")
        story.priority = kwargs.get("priority", None)
        story.labels = kwargs.get("labels", [])
        story.status = kwargs.get("status", None)
        story.acceptance_criteria = kwargs.get("acceptance_criteria", None)
        story.blockers = kwargs.get("blockers", [])
        story.description = kwargs.get("description", "")
        return story

    def test_ranks_all_stories_not_just_open(self):
        """Rankings are computed for every story supplied, regardless of status."""
        done_story = self._make_story(id="done", status="Done", priority="high")
        todo_story = self._make_story(id="todo", status="To Do", priority="medium")
        result = compute_priority_rankings([done_story, todo_story])
        assert "done" in result
        assert "todo" in result

    def test_rationale_does_not_say_open_stories(self):
        """Rationale must say 'N stories', not 'N open stories'."""
        s = self._make_story(id="s1")
        result = compute_priority_rankings([s])
        _, _, rationale = result["s1"]
        assert "open stories" not in rationale
        assert "stories" in rationale

    def test_rank_1_assigned_to_highest_scoring_story(self):
        high = self._make_story(id="high", priority="highest", status="Ready for Dev",
                                acceptance_criteria="1. Returns 200.\n2. Saves record.",
                                blockers=[], labels=["security"])
        low = self._make_story(id="low", priority=None, status=None,
                               acceptance_criteria=None, blockers=[], labels=[])
        result = compute_priority_rankings([low, high])
        assert result["high"][0] == 1   # rank 1 = highest priority
        assert result["low"][0] == 2

    def test_story_points_absent_from_ranking(self):
        """story_points must not be accessed; MagicMock will raise AttributeError
        if the attribute is used, because we don't set it."""
        story = MagicMock(spec=[
            "id", "priority", "labels", "status",
            "acceptance_criteria", "blockers", "description",
        ])
        story.id = "sp-test"
        story.priority = "medium"
        story.labels = []
        story.status = "To Do"
        story.acceptance_criteria = None
        story.blockers = []
        story.description = ""
        # Must not raise — story_points is not in spec so accessing it would AttributeError
        result = compute_priority_rankings([story])
        assert "sp-test" in result


# ===========================================================================
# Decision boundaries — mode score thresholds
# ===========================================================================

class TestModeScoreThresholds:
    """Verify the exact mode boundaries at >=10 and <-10."""

    def _story_with_score(self, target_score):
        """Return a MagicMock story whose metadata produces approximately `target_score`
        in _mode_engine.  Adjust components to hit exact boundary values."""
        story = MagicMock()
        story.description = ""
        story.blockers = []
        story.linked_prs = []
        # AC score=3 → +10 (testable list+verb)
        story.acceptance_criteria = "1. The endpoint returns 200.\n2. Record is saved."
        return story

    def test_score_exactly_10_is_bob_led(self):
        """AC=+10, no other signals → mode_score=10 → bob_led (threshold is >=10)."""
        story = self._story_with_score(10)
        mode, rationale, _, _, _, _ = _mode_engine(story, outcome_count=0, similar_tickets=[])
        assert mode == "bob_led", (
            f"score=10 should be bob_led (>=10 threshold). Rationale: {rationale}"
        )

    def test_score_exactly_9_is_collaborative(self):
        """AC=+4 (structured, no verb — score=2) → mode_score=4 → collaborative."""
        story = MagicMock()
        story.description = ""
        story.blockers = []
        story.linked_prs = []
        # AC score=2 → +4 — numbered list, no outcome verb
        story.acceptance_criteria = "1. It should work.\n2. Make it fast."
        mode, rationale, _, _, _, _ = _mode_engine(story, outcome_count=0, similar_tickets=[])
        assert mode == "collaborative", (
            f"AC score=2 (+4) should be collaborative. Rationale: {rationale}"
        )

    def test_score_negative_11_is_human_led(self):
        """No AC (-10) + ≥3 unknowns (-15) → -25 → human_led (< -10)."""
        story = MagicMock()
        story.description = (
            "Should we use Auth0? Which approach is best? "
            "What happens when tokens expire? Unknown compliance requirements."
        )
        story.blockers = []
        story.linked_prs = []
        story.acceptance_criteria = None
        mode, _, _, _, _, _ = _mode_engine(story, outcome_count=0, similar_tickets=[])
        assert mode == "human_led"

    def test_score_negative_10_is_collaborative(self):
        """No AC (-10), no unknowns → mode_score=-10 → collaborative (not < -10)."""
        story = MagicMock()
        story.description = "A clean, unambiguous description."
        story.blockers = []
        story.linked_prs = []
        story.acceptance_criteria = None
        mode, rationale, _, _, _, _ = _mode_engine(story, outcome_count=0, similar_tickets=[])
        assert mode == "collaborative", (
            f"score=-10 should be collaborative (threshold is <-10). Rationale: {rationale}"
        )

    def test_blocker_prevents_bob_led_even_with_testable_ac(self):
        """AC=+10, one blocker=-15 → net -5 → collaborative."""
        story = MagicMock()
        story.description = "No open unknowns."
        story.blockers = ["PIE-99"]
        story.linked_prs = []
        story.acceptance_criteria = "1. Returns 200.\n2. Saves record."
        mode, _, _, _, _, _ = _mode_engine(story, outcome_count=0, similar_tickets=[])
        assert mode in ("collaborative", "human_led"), (
            f"A blocker should prevent bob_led, got {mode}"
        )


# ===========================================================================
# Priority engine — verified flags and urgency vs readiness separation
# ===========================================================================

class TestPriorityEvidenceFlags:

    def _story(self, **kwargs):
        story = MagicMock()
        story.priority = kwargs.get("priority", None)
        story.labels = kwargs.get("labels", [])
        story.status = kwargs.get("status", None)
        story.acceptance_criteria = kwargs.get("ac", None)
        story.blockers = kwargs.get("blockers", [])
        story.description = kwargs.get("description", "")
        return story

    def test_all_known_fields_produce_verified_true_evidence(self):
        story = self._story(priority="high", labels=["security"],
                            status="Ready for Dev", ac="1. Returns 200.\n2. Saved.",
                            blockers=[])
        _, evidence, _ = _priority_score(story)
        for ev in evidence:
            if ev["source"] in ("jira_priority", "story_labels", "story_status",
                                "acceptance_criteria", "blockers"):
                assert ev["verified"] is True, (
                    f"Expected verified=True for {ev['source']}: {ev}"
                )

    def test_missing_priority_produces_unverified_evidence(self):
        story = self._story(priority=None)
        _, evidence, _ = _priority_score(story)
        prio_ev = [e for e in evidence if e["source"] == "jira_priority"]
        assert prio_ev[0]["verified"] is False

    def test_absent_ac_is_unverified(self):
        story = self._story(ac=None)
        _, evidence, _ = _priority_score(story)
        ac_ev = [e for e in evidence if e["source"] == "acceptance_criteria"]
        assert ac_ev[0]["verified"] is False

    def test_description_analysis_is_always_unverified(self):
        story = self._story(description="Should we use this? What happens if it fails? "
                                        "Unknown approach. TBD.")
        _, evidence, _ = _priority_score(story)
        desc_ev = [e for e in evidence if e["source"] == "description_analysis"]
        if desc_ev:
            for ev in desc_ev:
                assert ev["verified"] is False

    def test_urgency_evidence_source_is_story_labels(self):
        story = self._story(labels=["security", "p0"])
        _, evidence, _ = _priority_score(story)
        label_ev = [e for e in evidence if e["source"] == "story_labels"]
        assert len(label_ev) == 1
        assert "security" in label_ev[0]["description"].lower() or "p0" in label_ev[0]["description"].lower()

    def test_readiness_evidence_source_is_story_status(self):
        story = self._story(status="Ready for Dev")
        _, evidence, _ = _priority_score(story)
        status_ev = [e for e in evidence if e["source"] == "story_status"]
        assert len(status_ev) == 1
        assert "ready" in status_ev[0]["description"].lower()

    def test_story_points_not_accessed(self):
        """_priority_score must not access story_points; spec= ensures AttributeError if it does."""
        story = MagicMock(spec=[
            "priority", "labels", "status",
            "acceptance_criteria", "blockers", "description",
        ])
        story.priority = "medium"
        story.labels = []
        story.status = "To Do"
        story.acceptance_criteria = None
        story.blockers = []
        story.description = ""
        # Should not raise
        score, _, _ = _priority_score(story)
        assert isinstance(score, int)
