"""
Adversarial tests for _ac_quality().

These tests focus on cases where the regex detects structural signals that are
present in the text but do not make the criteria genuinely testable or verifiable.
The tests confirm the system's behaviour is honest about what was detected and
does NOT assert more than that.

Adversarial scenarios covered:
  1. Vague BDD — all three keywords present in order, but criteria are meaningless:
       "Given the system, when something happens, then it should work."
     The heuristic correctly scores this as well_structured (score=3) because the
     structural pattern was detected.  Tests confirm the evidence text does NOT
     claim the criteria are independently verifiable.

  2. Outcome verbs with no concrete expected result:
       "1. The API returns something."  → returns + list → score 3 (well_structured)
       "The endpoint returns a response." → returns (no list) → score 2 (structured)
     Neither tells you what the expected value is.  Tests confirm scores are
     consistent with the structural-only contract and the evidence text does not
     assert domain correctness.

  3. BDD with tautological content:
       "Given anything, when anything happens, then things work."
     Scores 3 because the pattern was found.  Tests confirm the label is
     "well_structured", not "testable".

  4. Contradictory list items that individually match structural patterns:
       "1. Returns 200.\n2. Returns 500 for the same request."
     Both items have a list item + outcome verb.  Score=3 is expected; the
     engine cannot detect logical contradiction.  Tests document this limitation
     explicitly.

  5. Structural pattern present in comments, not in criteria:
       "# Example: given/when/then\n1. It should work."
     The BDD pattern fires on the comment line.  Score=3.  Documents the
     known limitation that the regex is not context-aware.

  6. Score-3 evidence description must describe detected structure, not assert
     genuine testability or correctness.
"""

from __future__ import annotations

import pytest

from backend.services.recommendation_service import _ac_quality, _mode_engine
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_mode(ac: str | None, description: str = "No open unknowns.",
              blockers=None) -> tuple:
    story = MagicMock()
    story.acceptance_criteria = ac
    story.description = description
    story.blockers = blockers or []
    story.linked_prs = []
    return _mode_engine(story, outcome_count=0, similar_tickets=[])


def _mode_ac_evidence(ac: str | None) -> dict:
    _, _, evidence, _, _, _ = _run_mode(ac)
    items = [e for e in evidence if e["source"] == "acceptance_criteria"]
    assert len(items) == 1, f"Expected exactly 1 AC evidence item, got {items}"
    return items[0]


# ===========================================================================
# 1. Vague BDD scenarios
# ===========================================================================

class TestVagueBddScenarios:
    """
    When all three BDD keywords appear in order but the criteria carry no
    concrete expected result, the heuristic scores well_structured (3) because
    it detected the pattern.  Tests confirm scores are correct AND that evidence
    text does not overclaim testability.
    """

    def test_vague_bdd_scores_well_structured(self):
        score, label, _ = _ac_quality(
            "Given the system is running, when something happens, "
            "then it should work correctly."
        )
        assert score == 3
        assert label == "well_structured"

    def test_minimal_placeholder_bdd_scores_well_structured(self):
        score, label, _ = _ac_quality("Given X when Y then Z.")
        assert score == 3
        assert label == "well_structured"

    def test_tautological_bdd_scores_well_structured(self):
        score, label, _ = _ac_quality(
            "Given anything, when anything happens, then things work."
        )
        assert score == 3
        assert label == "well_structured"

    def test_bdd_with_vague_then_scores_well_structured(self):
        score, label, _ = _ac_quality(
            "Given a user is authenticated, when they access the page, "
            "then the page should load."
        )
        # "loads" is in _AC_OUTCOME_VERBS AND BDD triplet present → well_structured
        assert score == 3
        assert label == "well_structured"

    def test_vague_bdd_evidence_does_not_assert_domain_correctness(self):
        ev = _mode_ac_evidence(
            "Given the system, when something happens, then it should work correctly."
        )
        desc = ev["description"].lower()
        # Must not claim the criteria are independently verifiable or domain-correct
        assert "verifiable" not in desc or "not" in desc
        assert "correct" not in desc or "not assessed" in desc or "domain" in desc
        # Must describe what was detected
        assert "structural" in desc or "detected" in desc or "signal" in desc

    def test_vague_bdd_evidence_is_verified_true(self):
        """verified=True reflects that the structural pattern was actually found, nothing more."""
        ev = _mode_ac_evidence("Given X when Y then Z.")
        assert ev["verified"] is True  # we DID detect the pattern — that part is verified

    def test_vague_bdd_is_indistinguishable_from_real_bdd_by_score(self):
        """The heuristic cannot distinguish vague from specific BDD by design.
        This test documents the known limitation explicitly."""
        vague_score, _, _ = _ac_quality(
            "Given anything, when anything happens, then things work."
        )
        specific_score, _, _ = _ac_quality(
            "Given a valid JWT token in the Authorization header, "
            "when the user calls GET /api/profile, "
            "then the response status is 200 and the body contains user.id."
        )
        # Both score 3 — the heuristic is structural only
        assert vague_score == specific_score == 3


# ===========================================================================
# 2. Outcome verbs without concrete expected results
# ===========================================================================

class TestOutcomeVerbsWithoutConcreteResults:
    """
    An outcome verb (returns, saves, etc.) is detected as a structural signal.
    The system correctly scores the AC based on structure only and does NOT
    assert that the expected result is concrete or measurable.
    """

    def test_returns_something_with_list_scores_well_structured(self):
        score, label, _ = _ac_quality("1. The API returns something.")
        assert score == 3
        assert label == "well_structured"

    def test_returns_data_without_list_scores_structured(self):
        score, label, _ = _ac_quality("The endpoint returns a response.")
        assert score == 2
        assert label == "structured"

    def test_saves_without_specifying_what_scores_well_structured(self):
        score, label, _ = _ac_quality("1. The system saves the data.")
        assert score == 3
        assert label == "well_structured"

    def test_vague_outcome_verb_evidence_does_not_claim_specific_expected_value(self):
        ev = _mode_ac_evidence("1. The API returns something.")
        desc = ev["description"].lower()
        # Must not claim the expected value is specified or verifiable
        assert "specific" not in desc or "not" in desc
        # Must describe structural detection
        assert "structural" in desc or "detected" in desc or "signal" in desc

    def test_outcome_verb_alone_in_prose_scores_structured_not_well_structured(self):
        """A single outcome verb in prose with no list and no BDD → score 2, not 3."""
        score, label, _ = _ac_quality("The system should display something.")
        assert score == 2
        assert label == "structured"


# ===========================================================================
# 3. Contradictory list items
# ===========================================================================

class TestContradictoryListItems:
    """
    The heuristic cannot detect logical contradictions between list items.
    Tests document this as a known limitation.
    """

    def test_contradictory_items_score_well_structured(self):
        """Known limitation: contradictory items still score well_structured."""
        score, label, _ = _ac_quality(
            "1. Returns 200.\n2. Returns 500 for the same request."
        )
        assert score == 3
        assert label == "well_structured"

    def test_contradictory_items_evidence_does_not_resolve_contradiction(self):
        ev = _mode_ac_evidence(
            "1. Returns 200.\n2. Returns 500 for the same request."
        )
        desc = ev["description"].lower()
        # Evidence must not claim the criteria are consistent or correct
        assert "consistent" not in desc
        assert "correct" not in desc or "not assessed" in desc


# ===========================================================================
# 4. BDD pattern in comments or metadata, not in criteria
# ===========================================================================

class TestBddPatternInNonCriteriaContext:
    """
    The regex is not context-aware: if the BDD triplet appears anywhere in
    the text (including comments, examples, or headings), it triggers score 3.
    Tests document this known limitation.
    """

    def test_bdd_in_comment_triggers_well_structured(self):
        """Known limitation: BDD pattern in a comment fires the regex."""
        ac = "# Example format: given/when/then\n1. It should work."
        score, label, _ = _ac_quality(ac)
        # The regex finds the BDD pattern regardless of whether it's in a comment.
        # This is a known limitation; fixing it would require parsing context.
        assert score == 3
        assert label == "well_structured"

    def test_bdd_keywords_in_natural_sentence_order_triggers_match(self):
        """
        'Given that ... when ... then ...' triggers the BDD pattern even
        when the sentence is not a test scenario.
        """
        ac = (
            "Given the product requirements, when we consider performance, "
            "then we must ensure throughput."
        )
        score, label, _ = _ac_quality(ac)
        assert score == 3
        assert label == "well_structured"


# ===========================================================================
# 5. Score-3 evidence text must not overclaim
# ===========================================================================

class TestScoreThreeEvidenceText:
    """
    For every path that returns score=3 ("well_structured"), the evidence text
    added to mode_evidence must describe what was detected, not assert that
    the criteria are independently verifiable or domain-complete.
    """

    @pytest.mark.parametrize("ac", [
        # Full BDD
        "Given a user, when they log in, then a session is created.",
        # List + outcome verb
        "1. The endpoint returns 200.\n2. Record is saved.",
        # Vague BDD
        "Given anything, when anything happens, then things work.",
        # Outcome verb with no concrete result + list
        "1. The API returns something.",
        # BDD with tautological content
        "Given X when Y then Z.",
        # Real fixture ACs
        (
            "1. No secrets in source code.\n"
            "2. .env.example documents all required variables.\n"
            "3. Application starts correctly when environment variables are set.\n"
            "4. Existing integration tests pass unchanged."
        ),
    ])
    def test_score3_evidence_does_not_claim_testability(self, ac):
        ev = _mode_ac_evidence(ac)
        desc = ev["description"].lower()

        # The word "testable" alone in a positive assertion is banned
        # (acceptable only if preceded by negation like "not testable" or
        # qualified as "structurally")
        if "testable" in desc:
            # Must be qualified — "structurally testable" is now gone from the
            # template, but guard against accidental reintroduction
            assert "not assessed" in desc or "structural" in desc

        # Must describe detected structure
        assert "structural" in desc or "detected" in desc or "signal" in desc

        # Must acknowledge limits
        assert "not assessed" in desc or "structural" in desc or "domain" in desc

    def test_score3_label_is_well_structured_not_testable(self):
        """The score-3 label must be 'well_structured', not 'testable'."""
        for ac in [
            "Given X when Y then Z.",
            "1. Returns 200.\n2. Saved.",
            "Given a user, when they POST /items, then a 201 is returned.",
        ]:
            _, label, _ = _ac_quality(ac)
            assert label == "well_structured", (
                f"Expected label 'well_structured' for AC: {ac!r}, got {label!r}"
            )

    def test_score2_label_is_structured(self):
        for ac in [
            "1. It should work.",
            "The endpoint returns a response.",
            "- Item A.\n- Item B.",
        ]:
            _, label, _ = _ac_quality(ac)
            assert label == "structured", (
                f"Expected label 'structured' for AC: {ac!r}, got {label!r}"
            )
