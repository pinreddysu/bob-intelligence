"""
Recommendation service — Milestones 3 and 4a.

Deterministic, explainable rule engine that evaluates a story and produces:
  - Ticket prioritization: priority_rank, priority_rationale, priority_evidence
  - Execution mode: mode, mode_rationale, mode_evidence, mode_risks,
                    mode_counterevidence, uncertainty_note
  - Historical evidence (M4a): similar_tickets, supporting_prs,
                    evidence_confidence, code_analysis_notes

Design constraints (from plan):
  - story_points MUST NOT influence any recommendation output.
  - All evidence items trace to real story fields or verified historical records.
    Nothing is invented.
  - uncertainty_note is always explicit about absent evidence.
  - When fewer than 3 Outcome records exist, uncertainty_note says so.
  - When no similar resolved tickets are found, uncertainty_note says so.
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
from backend.services import historical_evidence_service


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

# Terminal Jira statuses — stories in these states are no longer actionable work
# and must be excluded from priority rankings.  The ranking purpose (per the plan)
# is "surface the single best next ticket from a list of open stories"; completed
# or cancelled work should never compete with in-flight or ready stories.
# Values are lowercased for case-insensitive comparison.
_STATUS_TERMINAL = frozenset({
    "done", "closed", "resolved", "won't fix", "wont fix",
    "cancelled", "canceled", "rejected", "duplicate",
})

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


# ---------------------------------------------------------------------------
# Acceptance criteria quality heuristic
# ---------------------------------------------------------------------------

# BDD scenario structure — requires all three keywords in order so that
# common English words ("when", "then", "given that") do not falsely match.
# Allows up to 300 characters between each keyword to accommodate multi-line
# and verbose BDD scenarios.
_AC_BDD = re.compile(
    r"\bgiven\b.{0,300}\bwhen\b.{0,300}\bthen\b",
    re.IGNORECASE | re.DOTALL,
)

# Observable outcome verbs — assert a verifiable result.
# These are structural hints, not proof of testability.  A list item like
# "1. It works." does not match because "works" is absent here.
_AC_OUTCOME_VERBS = re.compile(
    r"\b(returns?|responds?|displays?|shows?|renders?|loads?|rejects?|"
    r"redirects?|raises?|throws?|saves?|stores?|creates?|updates?|deletes?|"
    r"hides?|sends?|receives?|validates?|accepts?|starts?|stops?|"
    r"pass(?:es)?|fails?|triggers?|reads?|writes?|logs?|emits?)\b",
    re.IGNORECASE,
)

# Numbered or bulleted list items — each one is a candidate criterion.
_AC_LIST_ITEM = re.compile(
    r"(^\s*\d+[\.\)]\s|\n\s*\d+[\.\)]\s|^\s*[-*]\s|\n\s*[-*]\s)",
    re.MULTILINE,
)


def _ac_quality(ac: str | None) -> tuple[int, str, list[str]]:
    """
    Score acceptance criteria on observable structural signals, returning
    (score, label, reasons).

    The score measures detectable structure only.  It cannot determine
    whether individual criteria are domain-correct, non-contradictory,
    sufficiently specific, or actually verifiable in practice.

    Scores
    ------
    3  "well_structured" — BDD Given/When/Then triplet detected, OR a
                           numbered/bulleted list combined with at least one
                           outcome verb.  Both are structural indicators, not
                           proof that the criteria can be independently verified.
    2  "structured"      — List OR outcome verb present (but not both, no BDD).
    1  "present"         — Non-empty text with no detectable structure.
    0  "absent"          — Empty or whitespace only.

    The label reflects what the regex detected, nothing more.
    """
    text = (ac or "").strip()
    if not text:
        return 0, "absent", ["No acceptance criteria provided."]

    has_bdd = bool(_AC_BDD.search(text))
    has_list = bool(_AC_LIST_ITEM.search(text))
    has_outcome_verb = bool(_AC_OUTCOME_VERBS.search(text))

    reasons: list[str] = []
    if has_bdd:
        reasons.append("Given/When/Then scenario structure detected.")
    if has_list:
        reasons.append("Numbered or bulleted list of criteria detected.")
    if has_outcome_verb:
        reasons.append("Outcome verb(s) found (e.g. returns, saves, validates).")

    # Strong structural signal: full BDD triplet, or list + outcome verb together
    if has_bdd or (has_list and has_outcome_verb):
        if not reasons:
            reasons.append("Strong structural indicators present.")
        return 3, "well_structured", reasons

    # Partial structural signal: list only, or outcome verb in prose
    if has_list or has_outcome_verb:
        return 2, "structured", reasons

    # Text present but no structural indicators found
    reasons.append("Criteria are present but written as unstructured prose.")
    return 1, "present", reasons




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

    # 4. Acceptance criteria quality
    ac_score, ac_label, ac_reasons = _ac_quality(story.acceptance_criteria)
    reason_str = " ".join(ac_reasons)
    if ac_score == 3:
        score += 10
        evidence.append(_evidence(
            "acceptance_criteria",
            f"Acceptance criteria show strong structural signals ({ac_label}). {reason_str} "
            "Structure was detected; domain correctness and completeness are not assessed here.",
        ))
        rationale_parts.append("well-structured acceptance criteria present")
    elif ac_score == 2:
        score += 7
        evidence.append(_evidence(
            "acceptance_criteria",
            f"Acceptance criteria show partial structural signals ({ac_label}). "
            f"{reason_str}",
        ))
        rationale_parts.append("partially structured acceptance criteria present")
    elif ac_score == 1:
        score += 3
        evidence.append(_evidence(
            "acceptance_criteria",
            f"Acceptance criteria are present but unstructured ({ac_label}). "
            "Harder to verify independently.",
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

    The caller is responsible for passing only the stories that should compete
    in the ranking pool.  generate() pre-filters terminal-status stories
    (Done, Closed, Resolved, etc.) and then always re-adds the target story
    so a recommendation can still be produced for a terminal story — but that
    story's rank reflects competition only against other open stories, and it
    is surfaced explicitly in generate() rather than presented as an ordinary
    member of the actionable-work list.

    The priority score measures a combination of urgency (Jira priority,
    urgency labels) and readiness (status, AC quality, absence of blockers).
    It is a deliberate composite: a high-urgency story with blockers scores
    lower than a high-urgency story that is truly ready, because surfacing
    blocked work as "top priority" is misleading.  Consumers should read it
    as "most important AND most actionable now", not purely one or the other.

    Tie-breaking is deterministic: equal-score stories are ordered by story.id
    ascending so that rankings are stable across repeated calls and do not
    depend on database row order.
    """
    scored = [(s, _priority_score(s)) for s in stories]
    # Primary: higher score first.  Secondary: story.id ascending for stability.
    scored.sort(key=lambda x: (-x[1][0], x[0].id))

    result: dict[str, tuple[int, list, str]] = {}
    for rank, (story, (score, evidence, rationale)) in enumerate(scored, start=1):
        # Append rank context to rationale
        full_rationale = f"Ranked #{rank} of {len(stories)} stories. " + rationale
        result[story.id] = (rank, evidence, full_rationale)
    return result


# ---------------------------------------------------------------------------
# Mode engine
# ---------------------------------------------------------------------------


def _mode_engine(
    story: Story,
    outcome_count: int,
    similar_tickets: list[dict] | None = None,
) -> tuple[str, str, list, list, list, str]:
    """
    Return (mode, rationale, evidence, risks, counterevidence, uncertainty_note).
    story_points and story labels are never used — mode is driven by story
    structure signals and historical evidence, not org-specific label taxonomy.

    similar_tickets: pre-computed list from historical_evidence_service.find_similar().
    """
    evidence: list[dict] = []
    risks: list[dict] = []
    counterevidence: list[dict] = []
    uncertainty_parts: list[str] = []

    # --- Score accumulation -------------------------------------------------
    # Positive = toward bob_led, negative = toward human_led
    # 0 zone = collaborative
    mode_score = 0  # int: >=10 → bob_led, <-10 → human_led, else collaborative
    hist_delta_applied = 0  # tracks whether historical tickets moved the score

    # 1. Acceptance criteria quality
    ac_score, ac_label, ac_reasons = _ac_quality(story.acceptance_criteria)
    reason_str = " ".join(ac_reasons)
    if ac_score == 3:
        mode_score += 10
        evidence.append(_evidence(
            "acceptance_criteria",
            f"Acceptance criteria show strong structural signals ({ac_label}). {reason_str} "
            "Structure was detected; domain correctness and completeness are not assessed here.",
        ))
    elif ac_score == 2:
        mode_score += 4
        evidence.append(_evidence(
            "acceptance_criteria",
            f"Acceptance criteria show partial structural signals ({ac_label}). {reason_str}",
        ))
    elif ac_score == 1:
        mode_score -= 3
        evidence.append(_evidence(
            "acceptance_criteria",
            f"Acceptance criteria are present but unstructured ({ac_label}). "
            "Harder to verify automatically.",
            verified=False,
        ))
        risks.append(_risk(
            "Unstructured acceptance criteria increase the chance of "
            "misinterpreting the done condition.",
            severity="low",
        ))
    else:  # absent
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

    # 2. Description quality and open unknowns
    desc_unknowns = _count_unknowns(story.description or "")

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

    # 3. Blockers
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

    # 4. Linked PRs — record as context only; do not score on bare URL existence.
    # story.linked_prs contains PR URLs imported from Jira with no merge status,
    # test results, or outcome data.  Awarding a score bonus for an unverified URL
    # would conflate "a PR was mentioned" with "the PR was merged and succeeded."
    # GitHub enrichment (merge status, files changed) is deferred to M4b.
    if story.linked_prs:
        evidence.append(_evidence(
            "linked_prs",
            f"{len(story.linked_prs)} linked PR URL(s) recorded in Jira. "
            "Merge status, test results, and outcomes are not yet available "
            "(GitHub enrichment deferred to M4b). Not used in mode scoring.",
            verified=False,
        ))

    # 5. Historical outcomes signal
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

    # 6. Historical ticket signals (M4a)
    if similar_tickets is None:
        similar_tickets = []

    hist_delta, hist_evidence = historical_evidence_service.compute_mode_score_adjustment(
        similar_tickets
    )
    if hist_delta != 0 or hist_evidence:
        mode_score += hist_delta
        hist_delta_applied = hist_delta
        evidence.extend(hist_evidence)

    if not similar_tickets:
        uncertainty_parts.append("no similar resolved tickets found")

    # --- Determine mode -----------------------------------------------------
    if mode_score >= 10:
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
        f"Mode score: {mode_score} (>=10 = bob_led, <-10 = human_led, else collaborative). "
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
    # Always accurately describe what DID and DID NOT influence the recommendation.
    # Rule: if hist_delta_applied != 0 the historical adjustment MUST be disclosed
    # regardless of whether other uncertainty conditions (low outcome count, missing
    # similar tickets) are also present.  Omitting it when uncertainty_parts is
    # non-empty was a bug — the note said "metadata only" while history had already
    # moved the score.
    if not uncertainty_parts:
        if hist_delta_applied != 0:
            uncertainty_note = (
                "Recommendation is based on story metadata and historical ticket signals. "
                f"Historical evidence adjusted mode score by {hist_delta_applied:+d}. "
                "Linked PR merge status and test outcomes are not yet available."
            )
        else:
            uncertainty_note = (
                "Recommendation is based on story metadata (description, "
                "acceptance criteria, blockers). "
                "Similar resolved tickets were found but did not adjust the mode score. "
                "Linked PR merge status and test outcomes are not yet available."
            )
    else:
        # Uncertainty conditions exist; still disclose any historical adjustment.
        base = (
            "Recommendation confidence is reduced because: "
            + "; ".join(uncertainty_parts)
            + "."
        )
        if hist_delta_applied != 0:
            uncertainty_note = (
                base
                + f" Historical evidence adjusted mode score by {hist_delta_applied:+d}."
                + " Linked PR merge status and test outcomes are not yet available."
            )
        else:
            uncertainty_note = base + " Recommendation is based on story metadata only."

    return mode, rationale, evidence, risks, counterevidence, uncertainty_note


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate(story: Story, db: "Session") -> Recommendation:
    """
    Generate a Recommendation for the given story.

    Steps:
      1. Compute priority rank relative to all open stories in DB.
      2. Find semantically similar resolved tickets (M4a).
      3. Compute execution mode recommendation (with historical signal).
      4. Supersede any existing pending recommendation for this story.
      5. Persist and return the Recommendation record.

    Terminal-target behaviour:
      A story whose status is Done/Closed/Resolved/etc. is ordinarily excluded
      from the priority-ranking pool (completed work must not compete with
      actionable work).  However, when a recommendation is requested for such a
      story the caller expects a result, so the story is re-added to the pool
      before ranking and receives a valid priority_rank.  Its rank is never
      surfaced in the actionable-work list — the caller should note
      evidence_confidence and mode separately and treat the rank as "among open
      stories only" context.

    story_points is never read or used.
    mode_approval_status is always "pending" on creation.
    """
    # ── 1. Priority ranking ────────────────────────────────────────────────
    # Only open (non-terminal) stories compete in priority ranking.
    # A story with status "Done", "Closed", "Resolved", etc. is complete work
    # and should never displace an actionable story in the ranked list.
    # The target story is always included even if its own status is terminal,
    # so a recommendation can still be generated; the rank will simply reflect
    # that it competes only against other open stories.
    all_stories: list[Story] = db.query(Story).all()
    open_stories: list[Story] = [
        s for s in all_stories
        if (s.status or "").lower().strip() not in _STATUS_TERMINAL
    ]
    # Ensure the target story is always in the ranking pool
    if story not in open_stories:
        open_stories = open_stories + [story]
    priority_rankings = compute_priority_rankings(open_stories)
    priority_rank, priority_evidence, priority_rationale = priority_rankings.get(
        story.id, (len(open_stories), [], "Story not found in ranking list.")
    )

    # ── 2. Historical evidence (M4a) ───────────────────────────────────────
    similar_tickets = historical_evidence_service.find_similar(story, db)
    supporting_prs = historical_evidence_service.build_supporting_prs(similar_tickets)
    evidence_confidence = historical_evidence_service.compute_evidence_confidence(similar_tickets)

    # Strip linked_prs / was_reverted from the stored similar_tickets payload
    # (they are internal-use fields; the schema only requires the listed keys).
    stored_similar = [
        {
            "jira_key": t["jira_key"],
            "title": t["title"],
            "similarity_score": t["similarity_score"],
            "resolution": t["resolution"],
            "mode_used": t["mode_used"],
            "ac_met": t["ac_met"],
        }
        for t in similar_tickets
    ]

    # ── 3. Mode recommendation ─────────────────────────────────────────────
    outcome_count: int = db.query(Outcome).count()
    mode, mode_rationale, mode_evidence, mode_risks, mode_counterevidence, uncertainty_note = (
        _mode_engine(story, outcome_count, similar_tickets=similar_tickets)
    )

    # ── 4. Supersede any existing pending recommendation for this story ─────
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

    # ── 5. Persist new recommendation ──────────────────────────────────────
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
        # Historical evidence (M4a)
        similar_tickets=stored_similar,
        supporting_prs=supporting_prs,
        evidence_confidence=evidence_confidence,
        code_analysis_notes=None,  # populated in M4b
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
