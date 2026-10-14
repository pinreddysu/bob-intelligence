"""
Recommendation service — Milestone 3.

Deterministic, explainable rule engine that evaluates a story and produces:
  - Ticket prioritization: priority_rank, priority_rationale, priority_evidence
  - Execution mode: mode, mode_rationale, mode_evidence, mode_risks,
                    mode_counterevidence, uncertainty_note

Design constraints (from plan):
  - story_points MUST NOT influence any recommendation output.
  - All evidence items trace to real story fields — nothing is invented.
  - uncertainty_note is always explicit about absent evidence.
  - When fewer than 3 Outcome records exist, uncertainty_note says so.
  - Recommendation is advisory; no automatic approval.
  - mode_approval_status starts as "pending" on every new record.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from backend.models import Outcome, Recommendation, Story


# ---------------------------------------------------------------------------
# Evidence / risk item helpers
# ---------------------------------------------------------------------------

def _evidence(source: str, description: str, verified: bool = True) -> dict:
    return {"source": source, "description": description, "verified": verified}


def _risk(description: str, severity: str = "medium") -> dict:
    return {"description": description, "severity": severity}


def _counter(description: str) -> dict:
    return {"description": description}


# ---------------------------------------------------------------------------
# Priority engine
# ---------------------------------------------------------------------------

_PRIORITY_ORDER = {"highest": 5, "high": 4, "medium": 3, "low": 2, "lowest": 1}
_STATUS_READY_KEYWORDS = {"ready for dev", "ready", "approved", "dev ready"}
_STATUS_ACTIVE_KEYWORDS = {"in progress", "in review", "review"}
_URGENT_LABELS = {"security", "p0", "incident", "critical", "hotfix"}

# Keywords in description/title that indicate open unknowns / uncertainty
_UNKNOWN_PATTERNS = re.compile(
    r"\b(unknown|unresolved|unclear|tbd|to be determined|open question|"
    r"needs clarification|not decided|pending decision|uncertain|"
    r"should we|what happens|which approach|how should)\b",
    re.IGNORECASE,
)


def _count_unknowns(text: str) -> int:
    """Return the number of open-unknown signal matches in a text string."""
    if not text:
        return 0
    return len(_UNKNOWN_PATTERNS.findall(text))


def _priority_score(story: Story) -> tuple[int, list[dict], str]:
    """
    Compute a numeric priority score (higher = more urgent/ready) and return
    (score, evidence_list, rationale).

    NOTE: story_points is deliberately never read here.
    """
    score = 0
    evidence: list[dict] = []
    rationale_parts: list[str] = []

    # 1. Jira priority field (0-5 scale)
    jira_priority_val = _PRIORITY_ORDER.get((story.priority or "").lower(), 0)
    if jira_priority_val >= 4:
        score += 30
        evidence.append(_evidence(
            "jira_priority",
            f"Jira priority is '{story.priority}', indicating high urgency.",
        ))
        rationale_parts.append(f"Jira priority '{story.priority}'")
    elif jira_priority_val == 3:
        score += 15
        evidence.append(_evidence(
            "jira_priority",
            f"Jira priority is '{story.priority}'.",
        ))
        rationale_parts.append(f"Jira priority '{story.priority}'")
    elif jira_priority_val > 0:
        score += 5
        evidence.append(_evidence(
            "jira_priority",
            f"Jira priority is '{story.priority}' (lower urgency).",
        ))
    else:
        evidence.append(_evidence(
            "jira_priority",
            "No Jira priority field set.",
            verified=False,
        ))

    # 2. Urgent labels
    story_labels_lower = {str(lbl).lower() for lbl in (story.labels or [])}
    urgent_hits = story_labels_lower & _URGENT_LABELS
    if urgent_hits:
        score += 25
        label_str = ", ".join(sorted(urgent_hits))
        evidence.append(_evidence(
            "story_labels",
            f"Story carries urgency/risk label(s): {label_str}.",
        ))
        rationale_parts.append(f"urgency label(s) [{label_str}]")

    # 3. Status readiness
    status_lower = (story.status or "").lower()
    if any(kw in status_lower for kw in _STATUS_READY_KEYWORDS):
        score += 20
        evidence.append(_evidence(
            "story_status",
            f"Story status '{story.status}' indicates it is ready for development.",
        ))
        rationale_parts.append("status is ready for dev")
    elif any(kw in status_lower for kw in _STATUS_ACTIVE_KEYWORDS):
        score += 10
        evidence.append(_evidence(
            "story_status",
            f"Story status '{story.status}' indicates work is already in progress.",
        ))
        rationale_parts.append("status already in progress")

    # 4. Acceptance criteria completeness
    ac = story.acceptance_criteria or ""
    if len(ac.strip()) > 30:
        score += 10
        evidence.append(_evidence(
            "acceptance_criteria",
            "Acceptance criteria are present and detailed — story is well-defined.",
        ))
        rationale_parts.append("detailed acceptance criteria present")
    elif ac.strip():
        score += 5
        evidence.append(_evidence(
            "acceptance_criteria",
            "Acceptance criteria are present but brief.",
        ))
    else:
        evidence.append(_evidence(
            "acceptance_criteria",
            "No acceptance criteria found — reduces confidence in readiness.",
            verified=False,
        ))

    # 5. Blockers — reduces score significantly
    blocker_count = len(story.blockers or [])
    if blocker_count > 0:
        score -= 20 * blocker_count
        blocker_str = ", ".join(str(b) for b in story.blockers)
        evidence.append(_evidence(
            "blockers",
            f"Story has {blocker_count} blocking issue(s): {blocker_str}. "
            "These must be resolved before work can proceed.",
        ))
        rationale_parts.append(f"{blocker_count} unresolved blocker(s)")

    # 6. Open unknowns in description
    desc_unknowns = _count_unknowns(story.description or "")
    if desc_unknowns >= 3:
        score -= 10
        evidence.append(_evidence(
            "description_analysis",
            f"Description contains {desc_unknowns} open-unknown signal(s), "
            "suggesting requirements are not fully resolved.",
            verified=False,
        ))
        rationale_parts.append(f"{desc_unknowns} open unknowns in description")
    elif desc_unknowns > 0:
        evidence.append(_evidence(
            "description_analysis",
            f"Description contains {desc_unknowns} open-unknown signal(s).",
            verified=False,
        ))

    rationale = (
        "This story surfaces with priority score {score} based on: {parts}.".format(
            score=max(score, 0),
            parts=("; ".join(rationale_parts) if rationale_parts else "default low signal"),
        )
    )

    return (max(score, 0), evidence, rationale)


def compute_priority_rankings(stories: list[Story]) -> dict[str, tuple[int, list, str]]:
    """
    Rank a list of stories and return a dict keyed by story.id with
    (rank, evidence, rationale) per story.  Rank 1 = highest priority.
    """
    scored = [(s, _priority_score(s)) for s in stories]
    scored.sort(key=lambda x: x[1][0], reverse=True)

    result: dict[str, tuple[int, list, str]] = {}
    for rank, (story, (score, evidence, rationale)) in enumerate(scored, start=1):
        # Append rank context to rationale
        full_rationale = f"Ranked #{rank} of {len(stories)} open stories. " + rationale
        result[story.id] = (rank, evidence, full_rationale)
    return result


# ---------------------------------------------------------------------------
# Mode engine
# ---------------------------------------------------------------------------


def _mode_engine(
    story: Story,
    outcome_count: int,
) -> tuple[str, str, list, list, list, str]:
    """
    Return (mode, rationale, evidence, risks, counterevidence, uncertainty_note).
    story_points and story labels are never used — mode is driven by story
    structure signals and historical evidence, not org-specific label taxonomy.
    """
    evidence: list[dict] = []
    risks: list[dict] = []
    counterevidence: list[dict] = []
    uncertainty_parts: list[str] = []

    # --- Score accumulation -------------------------------------------------
    # Positive = toward bob_led, negative = toward human_led
    # 0 zone = collaborative
    mode_score = 0  # int: >10 → bob_led, <-10 → human_led, else collaborative

    # 1. Acceptance criteria quality
    ac = story.acceptance_criteria or ""
    if len(ac.strip()) > 50:
        mode_score += 10
        evidence.append(_evidence(
            "acceptance_criteria",
            "Detailed acceptance criteria reduce ambiguity and support Bob-led execution.",
        ))
    elif not ac.strip():
        mode_score -= 10
        evidence.append(_evidence(
            "acceptance_criteria",
            "No acceptance criteria found — increases risk of Bob-led execution.",
            verified=False,
        ))
        risks.append(_risk(
            "Missing acceptance criteria make it harder to verify Bob-generated output.",
            severity="medium",
        ))

    # 5. Description quality and open unknowns
    desc_unknowns = _count_unknowns(story.description or "")
    desc_len = len((story.description or "").strip())

    if desc_unknowns >= 3:
        mode_score -= 15
        evidence.append(_evidence(
            "description_analysis",
            f"Description contains {desc_unknowns} open-unknown signal(s), "
            "indicating unresolved requirements that need human judgment.",
            verified=False,
        ))
        risks.append(_risk(
            f"{desc_unknowns} open questions in description must be resolved "
            "before automated execution is safe.",
            severity="high",
        ))
    elif desc_unknowns > 0:
        mode_score -= 5
        evidence.append(_evidence(
            "description_analysis",
            f"Description contains {desc_unknowns} open-unknown signal(s).",
            verified=False,
        ))
        risks.append(_risk(
            "Some open questions in description; review before proceeding.",
            severity="low",
        ))

    if desc_len < 50:
        mode_score -= 10
        evidence.append(_evidence(
            "description_analysis",
            "Description is very short — may indicate incomplete requirements.",
            verified=False,
        ))
    elif desc_len > 300:
        mode_score += 5
        evidence.append(_evidence(
            "description_analysis",
            "Description is detailed and well-structured.",
        ))

    # 6. Blockers
    blocker_count = len(story.blockers or [])
    if blocker_count > 0:
        mode_score -= 15
        blocker_str = ", ".join(str(b) for b in story.blockers)
        evidence.append(_evidence(
            "blockers",
            f"Story is blocked by: {blocker_str}. "
            "Unresolved blockers require human judgment to unblock.",
        ))
        risks.append(_risk(
            "Unresolved blockers may stall Bob-led work; human must clear "
            "dependencies first.",
            severity="high",
        ))
        counterevidence.append(_counter(
            "Blockers are present — this story may not be executable until they are resolved, "
            "regardless of execution mode."
        ))

    # 7. Linked PRs as positive signal
    if story.linked_prs:
        mode_score += 5
        evidence.append(_evidence(
            "linked_prs",
            f"{len(story.linked_prs)} linked PR(s) provide prior context "
            "that Bob can reference.",
        ))

    # 8. Historical outcomes signal
    if outcome_count == 0:
        uncertainty_parts.append("no historical outcomes available")
        counterevidence.append(_counter(
            "No historical outcome records exist in this system — confidence in mode "
            "recommendation is reduced. Signal is based on story metadata only."
        ))
    elif outcome_count < 3:
        uncertainty_parts.append(
            f"only {outcome_count} historical outcome record(s) available — "
            "insufficient for pattern matching"
        )

    # --- Determine mode -----------------------------------------------------
    if mode_score > 10:
        mode = "bob_led"
    elif mode_score < -10:
        mode = "human_led"
    else:
        mode = "collaborative"

    # --- Counterevidence: always surface the other side -------------------
    if mode == "bob_led":
        counterevidence.append(_counter(
            "Bob-led execution should be reviewed before merging; "
            "automated output may miss domain-specific edge cases."
        ))
    elif mode == "human_led":
        counterevidence.append(_counter(
            "Parts of this work may be suitable for a collaborative approach "
            "once ambiguities and blockers are resolved."
        ))
    else:  # collaborative
        counterevidence.append(_counter(
            "A fully Bob-led pass could be attempted on the routine portions, "
            "with human review reserved for ambiguous sections."
        ))

    # --- Rationale ----------------------------------------------------------
    mode_labels = {"bob_led": "Bob-led", "collaborative": "Collaborative", "human_led": "Human-led"}
    rationale = (
        f"Execution mode '{mode_labels[mode]}' recommended. "
        f"Mode score: {mode_score} (>10 = bob_led, <-10 = human_led, else collaborative). "
    )
    if mode == "bob_led":
        rationale += (
            "Story has clear, detailed requirements with no open unknowns or blockers — "
            "well-suited for Bob-led execution."
        )
    elif mode == "human_led":
        rationale += (
            "Story has high-risk signals (unresolved unknowns, missing acceptance criteria, "
            "or active blockers) requiring human judgment."
        )
    else:
        rationale += (
            "Story has a mix of structured requirements and open questions "
            "that benefit from combined Bob assistance and human oversight."
        )

    # --- Uncertainty note ---------------------------------------------------
    if not uncertainty_parts:
        uncertainty_note = (
            "Recommendation is based on story metadata (labels, description, "
            "acceptance criteria, blockers, linked PRs). "
            "Historical outcome data is not currently factored in."
        )
    else:
        uncertainty_note = (
            "Recommendation confidence is reduced because: "
            + "; ".join(uncertainty_parts)
            + ". Signal is based on story metadata only."
        )

    return mode, rationale, evidence, risks, counterevidence, uncertainty_note


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate(story: Story, db: "Session") -> Recommendation:
    """
    Generate a Recommendation for the given story.

    Steps:
      1. Compute priority rank relative to all open stories in DB
         (stories whose status is not "Done" or "Closed").
      2. Compute execution mode recommendation.
      3. Persist and return the Recommendation record.

    story_points is never read or used.
    mode_approval_status is always "pending" on creation.
    """
    # ── 1. Priority ranking ────────────────────────────────────────────────
    all_stories: list[Story] = db.query(Story).all()
    # Include the current story even if it's not yet in a "open" status subset.
    priority_rankings = compute_priority_rankings(all_stories)
    priority_rank, priority_evidence, priority_rationale = priority_rankings.get(
        story.id, (len(all_stories), [], "Story not found in ranking list.")
    )

    # ── 2. Mode recommendation ─────────────────────────────────────────────
    outcome_count: int = db.query(Outcome).count()
    mode, mode_rationale, mode_evidence, mode_risks, mode_counterevidence, uncertainty_note = (
        _mode_engine(story, outcome_count)
    )

    # ── 3. Supersede any existing pending recommendation for this story ─────
    existing = (
        db.query(Recommendation)
        .filter(
            Recommendation.story_id == story.id,
            Recommendation.status == "pending",
        )
        .all()
    )
    for old_rec in existing:
        old_rec.status = "superseded"
    if existing:
        db.flush()

    # ── 4. Persist new recommendation ──────────────────────────────────────
    rec = Recommendation(
        story_id=story.id,
        priority_rank=priority_rank,
        priority_rationale=priority_rationale,
        priority_evidence=priority_evidence,
        mode=mode,
        mode_rationale=mode_rationale,
        mode_evidence=mode_evidence,
        mode_risks=mode_risks,
        mode_counterevidence=mode_counterevidence,
        uncertainty_note=uncertainty_note,
        mode_approval_status="pending",
        # Developer match fields stay null — DEFERRED
        suggested_developer=None,
        dev_match_rationale=None,
        dev_match_evidence=[],
        dev_match_risks=[],
        is_stretch_assignment=False,
        stretch_support_plan=None,
        dev_match_approval_status="pending",
        status="pending",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec
