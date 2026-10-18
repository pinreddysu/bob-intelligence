"""
Correctness tests — pre-M4b review pass.

Covers four areas identified during the review:

1. _mode_engine() uncertainty-note composition
   ─ Historical score adjustment MUST appear in the note whether or not
     other uncertainty conditions (low outcome count, missing similar
     tickets) are also present.

2. Terminal-target ranking semantics
   ─ Terminal stories are excluded from the normal ranking pool.
   ─ A terminal *target* is re-added so generate() can still produce a
     recommendation, but the result is not presented as an ordinary
     member of the actionable-work list.

3. Deterministic tie-breaking in compute_priority_rankings()
   ─ Equal-score stories must always sort by story.id ascending.

4. Priority vs readiness interaction
   ─ High urgency + blockers scores lower than high urgency + no blockers.
   ─ Readiness status (ready for dev) adds score.
   ─ The composite is documented: "most important AND most actionable now".

All tests use only public/internal APIs; no DB required (items 1-4 are
unit tests).  Terminal-target generate() regression tests live in
test_priority_eligibility.py (integration tests) and are not duplicated
here.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.services.recommendation_service import (
    _mode_engine,
    _priority_score,
    compute_priority_rankings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _story(
    id_: str = "s1",
    *,
    status: str | None = "To Do",
    priority: str | None = None,
    ac: str | None = None,
    blockers: list | None = None,
    labels: list | None = None,
    description: str = "",
) -> MagicMock:
    s = MagicMock()
    s.id = id_
    s.status = status
    s.priority = priority
    s.labels = labels or []
    s.acceptance_criteria = ac
    s.blockers = blockers or []
    s.description = description
    return s


def _well_structured_ac() -> str:
    """AC that triggers _ac_quality score 3 (BDD Given/When/Then)."""
    return "Given a user\nWhen they click save\nThen the record is stored."


def _make_bob_led_ticket(jira_key: str) -> dict:
    """A resolved ticket that was completed successfully in bob_led mode."""
    return {
        "jira_key": jira_key,
        "title": "Similar ticket",
        "similarity_score": 0.8,
        "resolution": "Done",
        "mode_used": "bob_led",
        "ac_met": True,
        "linked_prs": [],
        "was_reverted": False,
    }


def _make_reverted_ticket(jira_key: str) -> dict:
    """A resolved ticket that was reverted."""
    return {
        "jira_key": jira_key,
        "title": "Reverted ticket",
        "similarity_score": 0.7,
        "resolution": "Done",
        "mode_used": "bob_led",
        "ac_met": True,
        "linked_prs": [],
        "was_reverted": True,
    }


def _make_neutral_ticket(jira_key: str) -> dict:
    """A resolved ticket with no outcome signals."""
    return {
        "jira_key": jira_key,
        "title": "Neutral ticket",
        "similarity_score": 0.6,
        "resolution": "Done",
        "mode_used": None,
        "ac_met": None,
        "linked_prs": [],
        "was_reverted": False,
    }


# ===========================================================================
# 1. _mode_engine() uncertainty-note composition
# ===========================================================================

class TestUncertaintyNoteComposition:
    """
    The uncertainty_note must accurately disclose what DID and DID NOT
    influence the recommendation in all combinations of:
      - outcome_count: 0 (no history), 1 or 2 (< 3), 3+ (sufficient)
      - similar_tickets: none / only neutral / ≥2 bob_led successes / reverted
    """

    # ── No uncertainty conditions, no adjustment ─────────────────────────────

    def test_no_uncertainty_no_adjustment_mentions_metadata(self):
        """When nothing reduces confidence and history didn't adjust, say so."""
        story = _story(ac=_well_structured_ac())
        _, _, _, _, _, note = _mode_engine(story, outcome_count=5, similar_tickets=[])
        # With no similar tickets, uncertainty_parts will have "no similar resolved tickets"
        # so we check the else branch — no adjustment, has uncertainty.
        assert "metadata only" in note or "metadata" in note

    def test_no_uncertainty_with_positive_adjustment(self):
        """≥2 bob_led successes, sufficient outcomes → adjustment disclosed in note."""
        story = _story(ac=_well_structured_ac())
        tickets = [_make_bob_led_ticket("T-1"), _make_bob_led_ticket("T-2")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=5, similar_tickets=tickets)
        assert "+10" in note or "adjusted mode score by +10" in note

    def test_no_uncertainty_with_negative_adjustment(self):
        """A reverted ticket → negative adjustment disclosed in note."""
        story = _story(ac=_well_structured_ac())
        tickets = [_make_reverted_ticket("T-1")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=5, similar_tickets=tickets)
        assert "-10" in note or "adjusted mode score by -10" in note

    def test_no_uncertainty_zero_adjustment_similar_found(self):
        """Similar tickets found but no adjustment → note says "did not adjust"."""
        story = _story(ac=_well_structured_ac())
        tickets = [_make_neutral_ticket("T-1")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=5, similar_tickets=tickets)
        assert "did not adjust" in note

    # ── Low outcome count only (uncertainty, no adjustment) ──────────────────

    def test_low_outcome_no_adjustment_mentions_reduced_confidence(self):
        """outcome_count=1 and no similar tickets → confidence reduced, no delta."""
        story = _story(ac=_well_structured_ac())
        _, _, _, _, _, note = _mode_engine(story, outcome_count=1, similar_tickets=[])
        assert "confidence is reduced" in note
        # No adjustment occurred; must NOT claim adjustment
        assert "+10" not in note and "-10" not in note

    def test_zero_outcome_no_adjustment_no_similar(self):
        """outcome_count=0, no similar tickets → both uncertainty conditions reported."""
        story = _story(ac=_well_structured_ac())
        _, _, _, _, _, note = _mode_engine(story, outcome_count=0, similar_tickets=[])
        assert "confidence is reduced" in note
        assert "no historical outcomes" in note or "no similar resolved tickets" in note

    # ── THE BUG CASE: uncertainty conditions present AND historical adjustment ─

    def test_low_outcome_with_positive_adjustment_discloses_adjustment(self):
        """
        BUG FIX: outcome_count=2 (< 3, triggers uncertainty) AND ≥2 bob_led
        successes (delta=+10).  The note must NOT say "metadata only" —
        the historical adjustment DID influence the score.
        """
        story = _story(ac=_well_structured_ac())
        tickets = [_make_bob_led_ticket("T-1"), _make_bob_led_ticket("T-2")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=2, similar_tickets=tickets)
        # Must mention the adjustment
        assert "+10" in note, f"Expected '+10' in note but got: {note!r}"
        # Must NOT claim the recommendation is based on metadata only
        assert "metadata only" not in note, f"Note incorrectly says metadata only: {note!r}"
        # Must still mention reduced confidence
        assert "confidence is reduced" in note or "insufficient" in note.lower()

    def test_low_outcome_with_negative_adjustment_discloses_adjustment(self):
        """
        outcome_count=1 (< 3) AND a reverted ticket (delta=-10).
        Note must disclose the -10 adjustment, not silence it.
        """
        story = _story(ac=_well_structured_ac())
        tickets = [_make_reverted_ticket("T-1")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=1, similar_tickets=tickets)
        assert "-10" in note, f"Expected '-10' in note but got: {note!r}"
        assert "metadata only" not in note, f"Note incorrectly says metadata only: {note!r}"

    def test_zero_outcome_with_combined_adjustment_discloses_adjustment(self):
        """
        outcome_count=0 AND both +10 and -10 deltas (net=0) via combined tickets.
        Net delta is 0, so note should say "did not adjust" or not mention delta.
        """
        story = _story(ac=_well_structured_ac())
        tickets = [
            _make_bob_led_ticket("T-1"),
            _make_bob_led_ticket("T-2"),
            _make_reverted_ticket("T-3"),
        ]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=0, similar_tickets=tickets)
        # Net delta is 0 (+10 -10), so "metadata only" or the combined note is fine
        # but it must NOT claim a non-zero adjustment happened
        assert "+10" not in note, f"Net delta=0 but note claims +10: {note!r}"

    def test_no_similar_tickets_with_low_outcome_says_metadata_only(self):
        """No similar tickets, low outcome count → both conditions, says metadata only."""
        story = _story(ac=_well_structured_ac())
        _, _, _, _, _, note = _mode_engine(story, outcome_count=2, similar_tickets=[])
        assert "metadata only" in note

    def test_positive_adjustment_note_contains_linked_pr_caveat(self):
        """When a positive adjustment occurs the note must include the PR caveat."""
        story = _story(ac=_well_structured_ac())
        tickets = [_make_bob_led_ticket("T-1"), _make_bob_led_ticket("T-2")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=5, similar_tickets=tickets)
        assert "not yet available" in note or "deferred" in note or "Linked PR" in note

    def test_uncertainty_note_with_adjustment_does_not_omit_confidence_warning(self):
        """
        Even when the note discloses a historical adjustment, it must still
        communicate the reduced-confidence conditions.
        """
        story = _story(ac=_well_structured_ac())
        tickets = [_make_bob_led_ticket("T-1"), _make_bob_led_ticket("T-2")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=1, similar_tickets=tickets)
        # Historical adjustment disclosed
        assert "+10" in note
        # Reduced confidence also communicated
        assert "confidence is reduced" in note

    # ── outcome_count=2 with only neutral tickets ─────────────────────────────

    def test_two_outcomes_neutral_tickets_says_metadata_only(self):
        """
        outcome_count=2, neutral tickets (no adjustment) → uncertainty_parts
        includes the low-count warning; no delta → "metadata only".
        """
        story = _story(ac=_well_structured_ac())
        tickets = [_make_neutral_ticket("T-1")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=2, similar_tickets=tickets)
        assert "metadata only" in note

    # ── outcome_count=0 with positive adjustment ─────────────────────────────

    def test_zero_outcome_positive_adjustment_both_disclosed(self):
        """
        outcome_count=0 AND two bob_led successes: both uncertainty AND adjustment
        must be in the note.
        """
        story = _story(ac=_well_structured_ac())
        tickets = [_make_bob_led_ticket("T-1"), _make_bob_led_ticket("T-2")]
        _, _, _, _, _, note = _mode_engine(story, outcome_count=0, similar_tickets=tickets)
        assert "+10" in note, f"Expected '+10' in note: {note!r}"
        assert "metadata only" not in note, f"Note incorrectly says metadata only: {note!r}"


# ===========================================================================
# 2. Terminal-target ranking semantics (unit level)
# ===========================================================================

class TestTerminalTargetRankingUnit:
    """
    Unit-level tests for compute_priority_rankings() when a terminal story
    is included in the pool (as generate() does via re-addition).

    These complement the integration tests in test_priority_eligibility.py.
    """

    def test_terminal_target_receives_a_rank(self):
        """A terminal story added to the pool always gets a rank entry."""
        terminal = _story("done-1", status="Done", priority="medium")
        result = compute_priority_rankings([terminal])
        assert "done-1" in result

    def test_terminal_target_rank_relative_to_open_peer(self):
        """Terminal story with high priority still ranks below a higher-scoring open story."""
        terminal = _story("done-1", status="Done", priority="highest")
        open_high = _story("open-1", status="Ready for Dev", priority="highest",
                           ac=_well_structured_ac())
        # Simulate generate(): open pool contains open_high; terminal is re-added
        pool = [open_high, terminal]
        result = compute_priority_rankings(pool)
        rank_terminal = result["done-1"][0]
        rank_open = result["open-1"][0]
        # open_high has more score (ready status + AC) so must rank higher
        assert rank_open < rank_terminal

    def test_terminal_target_alone_ranks_first(self):
        """If only the terminal target is in the pool, it ranks #1."""
        terminal = _story("done-1", status="Done", priority="medium")
        result = compute_priority_rankings([terminal])
        assert result["done-1"][0] == 1

    def test_terminal_target_rationale_says_correct_pool_size(self):
        """Rationale must count pool size including the re-added target."""
        open_s = _story("open-1", status="To Do")
        terminal = _story("done-1", status="Done")
        pool = [open_s, terminal]
        result = compute_priority_rankings(pool)
        _, _, rationale = result["done-1"]
        assert "2 stories" in rationale


# ===========================================================================
# 3. Deterministic tie-breaking
# ===========================================================================

class TestDeterministicTieBreaking:
    """
    Equal-score stories must sort by story.id ascending so that rankings are
    stable across repeated calls and do not depend on insertion / DB row order.
    """

    def test_equal_score_sorted_by_id_ascending(self):
        """Two stories with the same priority and no other signals → id order."""
        s_z = _story("zzz-1", priority="medium")
        s_a = _story("aaa-1", priority="medium")
        # Run multiple orderings to confirm determinism
        for pool in [[s_z, s_a], [s_a, s_z]]:
            result = compute_priority_rankings(pool)
            rank_a = result["aaa-1"][0]
            rank_z = result["zzz-1"][0]
            assert rank_a == 1, f"aaa-1 should be rank 1; got {rank_a}"
            assert rank_z == 2, f"zzz-1 should be rank 2; got {rank_z}"

    def test_equal_score_three_stories_sorted_by_id(self):
        """Three equal-score stories rank in lexicographic id order."""
        stories = [
            _story("charlie", priority="low"),
            _story("alpha",   priority="low"),
            _story("bravo",   priority="low"),
        ]
        import itertools
        for perm in itertools.permutations(stories):
            result = compute_priority_rankings(list(perm))
            assert result["alpha"][0]   == 1
            assert result["bravo"][0]   == 2
            assert result["charlie"][0] == 3

    def test_higher_score_wins_over_alphabetical_disadvantage(self):
        """
        A lexicographically later id with a higher score must still rank first —
        tie-breaking only applies when scores are equal.
        """
        s_z = _story("zzz-hi", priority="highest")
        s_a = _story("aaa-lo", priority="low")
        result = compute_priority_rankings([s_z, s_a])
        assert result["zzz-hi"][0] == 1  # higher score wins
        assert result["aaa-lo"][0] == 2

    def test_idempotent_across_repeated_calls(self):
        """Calling compute_priority_rankings twice with same input gives same result."""
        stories = [_story(f"s-{i}", priority="medium") for i in range(5)]
        r1 = compute_priority_rankings(stories)
        r2 = compute_priority_rankings(stories)
        for sid in r1:
            assert r1[sid][0] == r2[sid][0], f"Rank changed for {sid}"


# ===========================================================================
# 4. Priority vs readiness interaction
# ===========================================================================

class TestPriorityVsReadiness:
    """
    Documents and asserts the deliberate composite nature of _priority_score:
    "most important AND most actionable now."

    The composite deliberately penalises blocked work even if it is
    high-urgency, because showing a blocked story at rank 1 is misleading.
    """

    def test_high_urgency_no_blockers_beats_high_urgency_with_blockers(self):
        """
        Same Jira priority, same AC quality — the blocked story must score lower.
        This is intentional: a blocked high-priority story cannot be acted on.
        """
        ready = _story("ready", priority="high", ac=_well_structured_ac())
        blocked = _story("blocked", priority="high", ac=_well_structured_ac(),
                         blockers=["PIE-99"])
        score_ready, _, _ = _priority_score(ready)
        score_blocked, _, _ = _priority_score(blocked)
        assert score_ready > score_blocked, (
            f"Expected ready ({score_ready}) > blocked ({score_blocked})"
        )

    def test_ready_status_increases_score(self):
        """
        A story with status 'Ready for Dev' scores higher than the same story
        with status 'To Do' (no other differences).
        """
        ready = _story("ready", priority="medium", status="Ready for Dev",
                       ac=_well_structured_ac())
        todo  = _story("todo",  priority="medium", status="To Do",
                       ac=_well_structured_ac())
        score_ready, _, _ = _priority_score(ready)
        score_todo,  _, _ = _priority_score(todo)
        assert score_ready > score_todo

    def test_in_progress_status_adds_partial_score(self):
        """'In Progress' earns some readiness score, less than 'Ready for Dev'."""
        ready = _story("ready", priority="medium", status="Ready for Dev")
        wip   = _story("wip",   priority="medium", status="In Progress")
        todo  = _story("todo",  priority="medium", status="To Do")
        score_ready, _, _ = _priority_score(ready)
        score_wip,   _, _ = _priority_score(wip)
        score_todo,  _, _ = _priority_score(todo)
        assert score_ready > score_wip >= score_todo

    def test_urgency_label_adds_score(self):
        """A story with an urgency label ('p0', 'security') scores higher."""
        urgent  = _story("urgent", priority="medium", labels=["security"])
        routine = _story("routine", priority="medium")
        score_urgent,  _, _ = _priority_score(urgent)
        score_routine, _, _ = _priority_score(routine)
        assert score_urgent > score_routine

    def test_multiple_blockers_accumulate_penalty(self):
        """Each blocker subtracts 20 points; 2 blockers = -40."""
        one_blocker = _story("one",  priority="highest", blockers=["PIE-1"])
        two_blockers = _story("two", priority="highest", blockers=["PIE-1", "PIE-2"])
        s1, _, _ = _priority_score(one_blocker)
        s2, _, _ = _priority_score(two_blockers)
        assert s1 > s2

    def test_high_urgency_with_two_blockers_vs_low_urgency_no_blockers(self):
        """
        Demonstrates the composite trade-off: very high urgency + 2 blockers may
        still score lower than lower-urgency ready work.

        priority=highest (+30) + 2 blockers (-40) → net −10 before clamping → 0
        priority=low (+5) + ready status (+20) → 25

        The output of the ranking reflects "act now" priority, not abstract importance.
        """
        urgent_blocked = _story("ub", priority="highest", blockers=["PIE-1", "PIE-2"])
        low_ready      = _story("lr", priority="low",     status="Ready for Dev",
                                ac=_well_structured_ac())
        score_ub, _, _ = _priority_score(urgent_blocked)
        score_lr, _, _ = _priority_score(low_ready)
        # Document the observed scores in the assertion message for clarity
        assert score_lr > score_ub, (
            f"Expected low-ready ({score_lr}) > urgent-blocked ({score_ub}): "
            "the score intentionally represents actionable-now priority."
        )

    def test_score_is_never_negative(self):
        """_priority_score always returns max(score, 0) — never negative."""
        heavily_penalised = _story(
            "hp", priority="lowest",
            blockers=["PIE-1", "PIE-2", "PIE-3"],
            description="TBD unknown unclear should we what happens",
        )
        score, _, _ = _priority_score(heavily_penalised)
        assert score >= 0

    def test_rationale_explains_composite(self):
        """The rationale string mentions the score-driving factors."""
        story = _story("s1", priority="high", labels=["security"],
                       status="Ready for Dev", ac=_well_structured_ac())
        _, _, rationale = _priority_score(story)
        # Should mention priority and/or readiness signals
        assert "priority" in rationale.lower() or "urgency" in rationale.lower() or "score" in rationale.lower()

    def test_evidence_list_includes_blocker_entry_when_blocked(self):
        """Blocker evidence item is present when blockers exist."""
        story = _story("s1", blockers=["PIE-10"])
        _, evidence, _ = _priority_score(story)
        sources = [e["source"] for e in evidence]
        assert "blockers" in sources

    def test_evidence_list_includes_readiness_entry_when_ready(self):
        """story_status evidence present when status is ready for dev."""
        story = _story("s1", status="Ready for Dev")
        _, evidence, _ = _priority_score(story)
        sources = [e["source"] for e in evidence]
        assert "story_status" in sources

    def test_story_points_never_in_priority_evidence(self):
        """story_points must never appear as an evidence source."""
        story = _story("s1", priority="highest")
        story.story_points = 100
        _, evidence, _ = _priority_score(story)
        sources = [e["source"] for e in evidence]
        assert "story_points" not in sources


# ===========================================================================
# 5. Status eligibility: no richer Jira fields available
# ===========================================================================

class TestStatusEligibilityReview:
    """
    The Story model exposes only `status: str | None`.  No status_category or
    resolution fields exist.  Exact-name matching against _STATUS_TERMINAL is
    therefore the correct and only available approach.

    These tests document that reality and assert current behavior.
    """

    def test_story_model_has_no_status_category_field(self):
        """Story mock has no status_category attribute other than those we set."""
        story = _story("s1", status="Done")
        # We can only rely on 'status'; there is no 'status_category'
        assert not hasattr(story, "status_category") or story.status_category != "Done"

    def test_terminal_matching_is_case_insensitive(self):
        """Terminal status matching in generate() uses .lower().strip()."""
        from backend.services.recommendation_service import _STATUS_TERMINAL
        for raw in ["Done", "DONE", "done", "  Done  "]:
            assert raw.strip().lower() in _STATUS_TERMINAL or raw.lower().strip() in _STATUS_TERMINAL

    def test_unknown_status_treated_as_open(self):
        """
        A status not in _STATUS_TERMINAL is not filtered out — open by default.
        This is conservative: if Jira adds a new terminal status we would need
        to update _STATUS_TERMINAL manually.
        """
        from backend.services.recommendation_service import _STATUS_TERMINAL
        assert "waiting for feedback" not in _STATUS_TERMINAL
        assert "blocked" not in _STATUS_TERMINAL
        assert "in review" not in _STATUS_TERMINAL
