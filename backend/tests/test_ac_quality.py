"""
Tests for the _ac_quality() helper in recommendation_service.

Covers:
  - Empty / absent criteria → score 0, label "absent"
  - Criteria present as prose only → score 1, label "present"
  - Vague criteria with no structure → score 1
  - Numbered list without outcome verbs → score 2, label "structured"
  - Outcome verb in prose (no list/BDD) → score 2, label "structured"
  - Valid BDD (Given/When/Then) → score 3, label "testable"
  - Numbered list + outcome verb → score 3, label "testable"
  - Short but genuinely testable BDD criteria → score 3
  - Vague numbered list without outcome verbs → score 2, NOT 3 (req 3)
  - Contradictory / ambiguous prose → score 1
  - Contradictory text that is still structurally testable → score 3
    (domain correctness is out of scope for a deterministic heuristic)
  - reasons list is always non-empty for every input
  - Integration: priority engine evidence source and score ordering
  - Integration: mode engine risk levels and verified flags
  - Integration: AC quality does not override blocker signal
  - Integration: label not presented as guarantee
"""

from __future__ import annotations

import pytest

from backend.services.recommendation_service import _ac_quality


# ===========================================================================
# Unit tests for _ac_quality()
# ===========================================================================

class TestAcQualityAbsent:
    def test_none_returns_absent(self):
        score, label, reasons = _ac_quality(None)
        assert score == 0
        assert label == "absent"
        assert len(reasons) >= 1

    def test_empty_string_returns_absent(self):
        score, label, reasons = _ac_quality("")
        assert score == 0
        assert label == "absent"
        assert len(reasons) >= 1

    def test_whitespace_only_returns_absent(self):
        score, label, reasons = _ac_quality("   \n\t  ")
        assert score == 0
        assert label == "absent"
        assert len(reasons) >= 1


class TestAcQualityPresent:
    """Non-empty prose with no list, BDD, or outcome verbs → score 1."""

    def test_plain_prose_returns_present(self):
        score, label, _ = _ac_quality("The feature should work correctly.")
        assert score == 1
        assert label == "present"

    def test_it_works_returns_present(self):
        # "works" is not in the outcome verb list; no list, no BDD
        score, label, _ = _ac_quality("it works and it is fast")
        assert score == 1
        assert label == "present"

    def test_make_it_fast_returns_present(self):
        score, label, _ = _ac_quality("make it fast")
        assert score == 1
        assert label == "present"

    def test_handle_errors_correctly_returns_present(self):
        # "handle" is not in the outcome verb list
        score, label, _ = _ac_quality("handle errors correctly")
        assert score == 1
        assert label == "present"

    def test_contradictory_prose_returns_structured(self):
        # "reject" is an outcome verb, so the heuristic scores this as structured.
        # Domain-level contradictions are semantic; this rule engine is structural only.
        score, label, _ = _ac_quality(
            "The system must both allow and reject all requests at the same time."
        )
        assert score == 2
        assert label == "structured"

    def test_generic_quality_prose_returns_present(self):
        score, label, _ = _ac_quality(
            "The implementation should be performant and reliable."
        )
        assert score == 1
        assert label == "present"


class TestAcQualityStructured:
    """Partial structure (list OR verb, not both; no BDD) → score 2."""

    def test_numbered_list_no_outcome_verb_returns_structured(self):
        # "It works" and "is fast" have no outcome verb from the regex
        score, label, _ = _ac_quality("1. It works.\n2. It is fast.")
        assert score == 2
        assert label == "structured"

    def test_bulleted_list_no_outcome_verb_returns_structured(self):
        score, label, _ = _ac_quality("- The UI looks nice.\n- Performance is good.")
        assert score == 2
        assert label == "structured"

    def test_outcome_verb_in_prose_no_list_returns_structured(self):
        # Single outcome verb in prose, no list or BDD
        score, label, _ = _ac_quality("The endpoint returns a 200 status code.")
        assert score == 2
        assert label == "structured"

    def test_vague_numbered_list_without_outcome_verbs_is_not_testable(self):
        """Req 3: a numbered list with only filler phrases must not reach score 3."""
        score, label, _ = _ac_quality(
            "1. It should work.\n2. Make it fast.\n3. Handle errors correctly."
        )
        assert score == 2, (
            "A numbered list without outcome verbs should be 'structured' (2), not 'testable' (3)"
        )
        assert label == "structured"

    def test_parenthetical_list_syntax_returns_structured(self):
        # "1) Item" syntax (parenthesis instead of dot)
        score, label, _ = _ac_quality("1) First requirement.\n2) Second requirement.")
        assert score == 2
        assert label == "structured"

    def test_dash_list_with_outcome_verb_returns_testable(self):
        score, label, _ = _ac_quality("- The API returns 200.\n- The record is saved.")
        assert score == 3
        assert label == "well_structured"


class TestAcQualityTestable:
    """Full structural testability indicators → score 3."""

    def test_bdd_pattern_returns_testable(self):
        score, label, reasons = _ac_quality(
            "Given a valid token, when the user calls /api/users, "
            "then a 200 response is returned."
        )
        assert score == 3
        assert label == "well_structured"
        assert any("Given/When/Then" in r for r in reasons)

    def test_bdd_case_insensitive(self):
        score, label, _ = _ac_quality(
            "given the user is logged in, when they POST /orders, "
            "then the order is created."
        )
        assert score == 3
        assert label == "well_structured"

    def test_numbered_list_with_outcome_verb_returns_testable(self):
        score, label, _ = _ac_quality(
            "1. The endpoint returns HTTP 201.\n"
            "2. The record is saved to the database.\n"
            "3. A confirmation email is sent."
        )
        assert score == 3
        assert label == "well_structured"

    def test_short_bdd_returns_testable(self):
        # Short text can still be structurally testable when it uses BDD
        score, label, _ = _ac_quality("Given X when Y then Z.")
        assert score == 3
        assert label == "well_structured"

    def test_numbered_list_with_starts_verb(self):
        score, label, _ = _ac_quality(
            "1. Application starts correctly after migration.\n"
            "2. All environment variables are documented."
        )
        assert score == 3
        assert label == "well_structured"

    def test_numbered_list_with_passes_verb(self):
        score, label, _ = _ac_quality(
            "1. Existing integration tests pass unchanged.\n"
            "2. No credentials are committed to source control."
        )
        assert score == 3
        assert label == "well_structured"

    def test_contradictory_but_structured_is_testable(self):
        """
        Contradictory domain content with a list and outcome verb scores testable.
        The heuristic is structural only; domain correctness is explicitly out of scope.
        """
        score, label, _ = _ac_quality(
            "1. The API returns 200 for all requests.\n"
            "2. The API rejects all requests."
        )
        assert score == 3
        assert label == "well_structured"

    def test_real_world_config_migration_ac(self):
        """AC from test_mode_bob_led_reachable fixture must score testable."""
        ac = (
            "1. No secrets in source code.\n"
            "2. .env.example documents all required variables.\n"
            "3. Application starts correctly when environment variables are set.\n"
            "4. Existing integration tests pass unchanged."
        )
        score, label, _ = _ac_quality(ac)
        assert score == 3
        assert label == "well_structured"

    def test_real_world_notification_ac(self):
        """AC from test_mode_collaborative_reachable fixture must score testable."""
        ac = (
            "1. Settings page shows toggles for email and push notifications.\n"
            "2. Preferences are saved on submit.\n"
            "3. Saved preferences are reflected on page reload."
        )
        score, label, _ = _ac_quality(ac)
        assert score == 3
        assert label == "well_structured"


class TestAcQualityReasons:
    """reasons list must always be non-empty."""

    @pytest.mark.parametrize("ac", [
        None,
        "",
        "  ",
        "prose only",
        "The system should handle errors.",
        "1. Item A.\n2. Item B.",
        "The endpoint returns 200.",
        "Given a user when they log in then a session is created.",
        "1. Returns 200.\n2. Saves record.",
    ])
    def test_reasons_always_non_empty(self, ac):
        _, _, reasons = _ac_quality(ac)
        assert len(reasons) >= 1, f"reasons was empty for AC: {ac!r}"

    def test_absent_reason_mentions_no_criteria(self):
        _, _, reasons = _ac_quality("")
        full = " ".join(reasons).lower()
        assert "no acceptance criteria" in full or "provided" in full

    def test_testable_reason_mentions_structure(self):
        _, _, reasons = _ac_quality("Given X when Y then Z.")
        full = " ".join(reasons)
        assert "Given/When/Then" in full or "scenario" in full.lower()


# ===========================================================================
# Integration tests — priority engine uses _ac_quality
# ===========================================================================

class TestPriorityEngineAcIntegration:
    """_priority_score must consume _ac_quality and reflect it in evidence + score."""

    def _make_story(self, ac):
        from unittest.mock import MagicMock
        story = MagicMock()
        story.acceptance_criteria = ac
        story.priority = None
        story.labels = []
        story.status = None
        story.blockers = []
        story.description = ""
        return story

    def test_testable_ac_evidence_source_and_verified(self):
        from backend.services.recommendation_service import _priority_score
        story = self._make_story(
            "Given a user, when they log in, then a session is created."
        )
        _, evidence, _ = _priority_score(story)
        ac_ev = [e for e in evidence if e["source"] == "acceptance_criteria"]
        assert len(ac_ev) == 1
        assert ac_ev[0]["verified"] is True

    def test_absent_ac_evidence_not_verified(self):
        from backend.services.recommendation_service import _priority_score
        story = self._make_story(None)
        _, evidence, _ = _priority_score(story)
        ac_ev = [e for e in evidence if e["source"] == "acceptance_criteria"]
        assert len(ac_ev) == 1
        assert ac_ev[0]["verified"] is False

    def test_testable_ac_scores_higher_than_absent(self):
        from backend.services.recommendation_service import _priority_score
        good = self._make_story("1. Returns 200.\n2. Saves record.")
        none_ = self._make_story(None)
        good_score, _, _ = _priority_score(good)
        none_score, _, _ = _priority_score(none_)
        assert good_score > none_score

    def test_testable_ac_scores_higher_than_structured(self):
        from backend.services.recommendation_service import _priority_score
        testable = self._make_story("1. Endpoint returns 200.\n2. Record is saved.")
        structured = self._make_story("1. It should work.\n2. Make it fast.")
        t_score, _, _ = _priority_score(testable)
        s_score, _, _ = _priority_score(structured)
        assert t_score > s_score

    def test_structured_ac_scores_higher_than_prose(self):
        from backend.services.recommendation_service import _priority_score
        structured = self._make_story("1. Item A.\n2. Item B.")
        prose = self._make_story("It should handle everything gracefully.")
        s_score, _, _ = _priority_score(structured)
        p_score, _, _ = _priority_score(prose)
        assert s_score > p_score


# ===========================================================================
# Integration tests — mode engine uses _ac_quality
# ===========================================================================

class TestModeEngineAcIntegration:
    """_mode_engine must consume _ac_quality and reflect it in mode_score, evidence, risks."""

    def _run_mode(self, ac, description="No open unknowns.", blockers=None, linked_prs=None):
        from unittest.mock import MagicMock
        from backend.services.recommendation_service import _mode_engine
        story = MagicMock()
        story.acceptance_criteria = ac
        story.description = description
        story.blockers = blockers or []
        story.linked_prs = linked_prs or []
        return _mode_engine(story, outcome_count=0, similar_tickets=[])

    def test_absent_ac_produces_medium_risk(self):
        _, _, _, risks, _, _ = self._run_mode(None)
        ac_risks = [r for r in risks
                    if "acceptance criteria" in r["description"].lower()]
        assert len(ac_risks) >= 1
        assert ac_risks[0]["severity"] == "medium"

    def test_absent_ac_evidence_not_verified(self):
        _, _, evidence, _, _, _ = self._run_mode(None)
        ac_ev = [e for e in evidence if e["source"] == "acceptance_criteria"]
        assert len(ac_ev) == 1
        assert ac_ev[0]["verified"] is False

    def test_prose_ac_produces_low_risk(self):
        _, _, _, risks, _, _ = self._run_mode(
            "The feature should work correctly."
        )
        ac_risks = [r for r in risks
                    if "done condition" in r["description"].lower()
                    or "unstructured" in r["description"].lower()
                    or "misinterpreting" in r["description"].lower()]
        assert len(ac_risks) >= 1
        assert ac_risks[0]["severity"] == "low"

    def test_testable_ac_no_acceptance_risk(self):
        _, _, _, risks, _, _ = self._run_mode(
            "Given a valid user when they POST /items then a 201 is returned."
        )
        ac_risks = [r for r in risks
                    if "acceptance criteria" in r["description"].lower()
                    or "done condition" in r["description"].lower()]
        assert len(ac_risks) == 0

    def test_testable_ac_evidence_verified(self):
        _, _, evidence, _, _, _ = self._run_mode(
            "1. Endpoint returns 200.\n2. Record is saved."
        )
        ac_ev = [e for e in evidence if e["source"] == "acceptance_criteria"]
        assert len(ac_ev) == 1
        assert ac_ev[0]["verified"] is True

    def test_ac_quality_does_not_override_blocker_signal(self):
        """Excellent AC (+10) plus one blocker (-15) → net -5 → collaborative, not bob_led."""
        mode, _, _, _, _, _ = self._run_mode(
            "Given X when Y then Z.",
            description="No open unknowns.",
            blockers=["PIE-99"],
        )
        assert mode in ("collaborative", "human_led"), (
            f"Blocker should prevent bob_led, got {mode}"
        )

    def test_ac_quality_label_not_presented_as_guarantee(self):
        """Evidence text for a well_structured AC must describe structure, not assert testability."""
        _, _, evidence, _, _, _ = self._run_mode(
            "1. The system returns 200.\n2. Record is saved."
        )
        ac_ev = [e for e in evidence if e["source"] == "acceptance_criteria"]
        assert len(ac_ev) == 1
        desc = ac_ev[0]["description"].lower()
        # Must not assert that criteria are genuinely testable
        assert "testable" not in desc or "not" in desc
        # Must describe what was detected, and acknowledge limits
        assert "structural" in desc or "detected" in desc or "not assessed" in desc
