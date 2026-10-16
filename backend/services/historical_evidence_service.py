"""
Historical evidence service — Milestones 4a and 4b.

Responsibilities (M4a):
  1. find_similar(story, db)  — TF-IDF cosine similarity between the new story
     and every ResolvedTicket in the database; returns up to 5 tickets with
     similarity_score ≥ 0.25, ordered by score descending.
  2. build_supporting_prs(resolved_tickets) — collect the union of linked_prs
     from the matched resolved tickets (de-duplicated by URL).
  3. compute_evidence_confidence(similar_tickets) — "high" / "medium" / "low" / "none"
     based on how many similar tickets have outcome signals (mode_used + ac_met).

Responsibilities (M4b — NEW):
  4. enrich_prs_with_github(supporting_prs, story, similar_tickets_full, db)
     — For each PR URL in supporting_prs, call github_service.fetch_pr_evidence()
       and optionally llm_service.analyze_pr(). Returns enriched SupportingPRItem
       dicts and a list of source_warning strings. Stores PREvidence records in DB.
  5. collect_outcome_evidence(similar_tickets_full, db)
     — Fetch Outcome records linked to the Story records of similar resolved tickets.
       Returns (evidence_items, risk_items) for consumption by the mode engine.
  6. collect_session_evidence(similar_tickets_full, db)
     — Fetch BobSession records for the same story_ids. Returns (evidence_items, risk_items).

Design constraints:
  - story_points MUST NOT influence any output.
  - Merged PRs and passing CI are NOT treated as proof that AC were met.
  - GitHub enrichment fails gracefully; partial evidence is recorded with
    source_warning rather than silently omitted or invented.
  - Outcome / BobSession signals are advisory and do not override scoring rules.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from backend.models import BobSession, Outcome, PREvidence, ResolvedTicket, Story
from backend.services import github_service, llm_service


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "as", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "it", "its", "that",
    "this", "these", "those", "from", "by", "not", "no", "if", "then",
    "we", "i", "you", "he", "she", "they", "our", "your", "their",
})


def _tokenise(text: str) -> list[str]:
    """Lowercase, split on non-alpha-numeric boundaries, remove stop words."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _story_text(story: Story) -> str:
    """Concatenate the searchable fields of a Story into a single string."""
    parts = [
        story.title or "",
        story.description or "",
        story.acceptance_criteria or "",
        " ".join(str(lbl) for lbl in (story.labels or [])),
    ]
    return " ".join(parts)


def _ticket_text(ticket: ResolvedTicket) -> str:
    """Concatenate the searchable fields of a ResolvedTicket into a single string."""
    parts = [
        ticket.title or "",
        ticket.description or "",
        " ".join(str(lbl) for lbl in (ticket.labels or [])),
    ]
    return " ".join(parts)


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity (pure Python, no external deps)
# ---------------------------------------------------------------------------

def _tf(tokens: list[str]) -> dict[str, float]:
    """Return term-frequency dict for a token list."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


def _idf(corpus_tf: list[dict[str, float]]) -> dict[str, float]:
    """
    Return inverse-document-frequency dict.
    idf(t) = log((1 + N) / (1 + df(t))) + 1   (smoothed)
    """
    n = len(corpus_tf)
    df: Counter = Counter()
    for doc_tf in corpus_tf:
        for term in doc_tf:
            df[term] += 1
    return {
        term: math.log((1.0 + n) / (1.0 + count)) + 1.0
        for term, count in df.items()
    }


def _tfidf_vector(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    """Return TF-IDF vector for a document given its TF and the corpus IDF."""
    return {term: tf_val * idf.get(term, 1.0) for term, tf_val in tf.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(vec_a.get(t, 0.0) * v for t, v in vec_b.items())
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

_SIMILARITY_THRESHOLD = 0.1
_MAX_RESULTS = 5


def find_similar(
    story: Story,
    db: "Session",
) -> list[dict]:
    """
    Find up to 5 ResolvedTicket records whose text is most similar to `story`,
    using TF-IDF cosine similarity.  Only tickets with similarity ≥ 0.25 are
    returned, ordered by score descending.

    Returns a list of dicts with keys:
        jira_key, title, similarity_score, resolution, mode_used, ac_met,
        linked_prs, was_reverted

    When the corpus is empty or no ticket meets the threshold, returns [].
    story_points is never read.
    """
    tickets: list[ResolvedTicket] = db.query(ResolvedTicket).all()
    if not tickets:
        return []

    story_tokens = _tokenise(_story_text(story))
    ticket_texts = [_tokenise(_ticket_text(t)) for t in tickets]

    # Build corpus TF for IDF computation (include query doc for smoothing)
    all_tf = [_tf(tokens) for tokens in [story_tokens] + ticket_texts]
    idf = _idf(all_tf)

    query_vec = _tfidf_vector(_tf(story_tokens), idf)

    scored: list[tuple[float, ResolvedTicket]] = []
    for ticket, tokens in zip(tickets, ticket_texts):
        doc_vec = _tfidf_vector(_tf(tokens), idf)
        score = _cosine_similarity(query_vec, doc_vec)
        if score >= _SIMILARITY_THRESHOLD:
            scored.append((score, ticket))

    scored.sort(key=lambda x: x[0], reverse=True) 
    '''
    the process is find all the tickets from past and ongoing ticket then 
    tokenize and remove uncessary words and combine AC, title, label, and 
    desc. Count the terms that are in ongoing ticket and all the past tickets
    _tf and store each story dict in list[story1 dict, paststory dict1...].
    then count it by combining all of them the terms and give them a score
    then compare using tfidf vector current ticket terms and value with combo
    of past + current terms count and give a score vector for current ticket. 
    then do the same for all the past ticket. whichever one is close vector 
    to current ranked on top and return top 5
    '''
    top = scored[:_MAX_RESULTS]

    return [
        {
            "jira_key": ticket.jira_key,
            "title": ticket.title,
            "similarity_score": round(score, 4),
            "resolution": ticket.resolution,
            "mode_used": ticket.mode_used,
            "ac_met": ticket.ac_met,
            "linked_prs": list(ticket.linked_prs or []),
            "was_reverted": ticket.was_reverted,
        }
        for score, ticket in top
    ]


def build_supporting_prs(similar_tickets: list[dict]) -> list[dict]:
    """
    Collect the union of linked_prs from similar tickets.

    Each PR URL becomes a base dict; GitHub enrichment happens in
    enrich_prs_with_github() (M4b).  De-duplicated by URL.
    """
    seen: set[str] = set()
    result: list[dict] = []
    for ticket in similar_tickets:
        for pr_url in ticket.get("linked_prs", []):
            if pr_url and pr_url not in seen:
                seen.add(pr_url)
                result.append({
                    "url": pr_url,
                    "merged": None,
                    "files_changed": [],
                    "title": None,
                    # M4b fields — populated by enrich_prs_with_github()
                    "state": None,
                    "test_files_present": None,
                    "was_reverted": None,
                    "ci_checks": [],
                    "diff_summary": None,
                    "source_warning": None,
                    "verified": False,
                })
    return result


def compute_evidence_confidence(similar_tickets: list[dict]) -> str:
    """
    Determine evidence confidence level from the matched similar tickets.

    "high"   — ≥3 similar tickets have mode_used and ac_met populated
    "medium" — 1–2 similar tickets have mode_used and ac_met populated
    "low"    — similar tickets exist but none have outcome signals
    "none"   — no similar tickets found
    """
    if not similar_tickets:
        return "none"
    #what if ther is no mode used
    with_outcomes = sum(
        1 for t in similar_tickets
        if t.get("mode_used") is not None and t.get("ac_met") is not None
    )

    if with_outcomes >= 3:
        return "high"
    if with_outcomes >= 1:
        return "medium"
    return "low"


def compute_mode_score_adjustment(similar_tickets: list[dict]) -> tuple[int, list[dict]]:
    """
    Compute the mode score adjustment and evidence items contributed by
    historical ticket signals.

    Rules (from plan):
      +10  when ≥2 similar tickets have mode_used="bob_led" and ac_met=True
      -10  when ≥1 similar ticket has was_reverted=True

    Returns (score_delta, evidence_items).
    evidence_items have the standard {source, description, verified} shape.
    """
    if not similar_tickets:
        return 0, []

    delta = 0
    items: list[dict] = []
    #what about other modes?
    bob_led_successes = [
        t for t in similar_tickets
        if t.get("mode_used") == "bob_led" and t.get("ac_met") is True
    ]
    if len(bob_led_successes) >= 2:
        keys = ", ".join(t["jira_key"] for t in bob_led_successes)
        delta += 10
        items.append({
            "source": "historical_tickets",
            "description": (
                f"{len(bob_led_successes)} similar resolved ticket(s) ({keys}) "
                "were completed successfully in bob_led mode — positive historical signal."
            ),
            "verified": True,
        })

    reverted = [t for t in similar_tickets if t.get("was_reverted") is True]
    if reverted:
        keys = ", ".join(t["jira_key"] for t in reverted)
        delta -= 10
        items.append({
            "source": "historical_tickets",
            "description": (
                f"Similar resolved ticket(s) ({keys}) were reverted — "
                "historical risk signal for this type of work."
            ),
            "verified": True,
        })

    return delta, items


# ---------------------------------------------------------------------------
# M4b — GitHub PR enrichment
# ---------------------------------------------------------------------------

def enrich_prs_with_github(
    supporting_prs: list[dict],
    story: "Story",
    similar_tickets_full: list[dict],
    db: "Session",
) -> tuple[list[dict], list[str]]:
    """
    Enrich each PR in supporting_prs with GitHub metadata and optional LLM analysis.

    For each PR URL:
      1. Call github_service.fetch_pr_evidence() — returns partial evidence when
         GITHUB_TOKEN is absent or API errors occur.
      2. If LLM_API_KEY is configured, call llm_service.analyze_pr() for richer
         diff_summary and code_analysis_notes.
      3. Persist a PREvidence record to the database.
      4. If LLM says relevant=False, exclude the PR from the returned list.

    Returns (enriched_prs, warnings):
      - enriched_prs: list of dicts ready for storing as Recommendation.supporting_prs
      - warnings: list of source_warning strings collected across all PRs

    Design constraints:
      - merged=True is NEVER treated as proof AC were met.
      - Passing CI checks are recorded but not labelled as AC proof.
      - All unverifiable fields remain None.
      - Never raises — all errors captured as source_warning entries.
    """
    enriched: list[dict] = []
    warnings: list[str] = []

    # Build a lookup: pr_url → jira_key + ticket metadata for LLM context
    url_to_ticket: dict[str, dict] = {}
    for ticket in similar_tickets_full:
        for pr_url in ticket.get("linked_prs", []):
            if pr_url and pr_url not in url_to_ticket:
                url_to_ticket[pr_url] = ticket

    for pr_base in supporting_prs:
        url = pr_base.get("url", "")
        if not url:
            continue

        # ── GitHub enrichment ──────────────────────────────────────────────
        gh_evidence = github_service.fetch_pr_evidence(url)
        if gh_evidence.get("source_warning"):
            warnings.append(gh_evidence["source_warning"])

        # ── LLM analysis (optional) ────────────────────────────────────────
        llm_analysis: "llm_service.LLMAnalysis | None" = None
        llm_warning: str | None = None

        ticket_ctx = url_to_ticket.get(url, {})
        llm_analysis, llm_warning = llm_service.analyze_pr(
            story_title=story.title or "",
            story_description=story.description,
            story_ac=story.acceptance_criteria,
            pr_title=gh_evidence.get("title"),
            pr_files=gh_evidence.get("files_changed") or [],
            pr_merged=gh_evidence.get("merged"),
            pr_was_reverted=gh_evidence.get("was_reverted"),
            resolved_ticket_title=ticket_ctx.get("title"),
            resolved_ticket_mode=ticket_ctx.get("mode_used"),
            resolved_ticket_ac_met=ticket_ctx.get("ac_met"),
        )
        if llm_warning:
            # Only record distinct LLM warnings once
            if llm_warning not in warnings:
                warnings.append(llm_warning)

        # If LLM says not relevant, skip this PR from the result set
        if llm_analysis is not None and llm_analysis.relevant is False:
            _persist_pr_evidence(
                url=url,
                gh=gh_evidence,
                llm=llm_analysis,
                story=story,
                ticket_ctx=ticket_ctx,
                db=db,
            )
            continue

        # Apply LLM output to evidence fields (prefer LLM over pattern-match)
        diff_summary = (llm_analysis.diff_summary if llm_analysis else None) or gh_evidence.get("diff_summary")
        code_analysis_notes = (llm_analysis.code_analysis_notes if llm_analysis else None)
        test_files_present = (
            llm_analysis.has_tests if (llm_analysis and llm_analysis.has_tests is not None)
            else gh_evidence.get("test_files_present")
        )

        enriched_pr = {
            "url": url,
            "title": gh_evidence.get("title"),
            "merged": gh_evidence.get("merged"),
            "files_changed": gh_evidence.get("files_changed") or [],
            "state": gh_evidence.get("state"),
            "test_files_present": test_files_present,
            "was_reverted": gh_evidence.get("was_reverted"),
            "ci_checks": gh_evidence.get("ci_checks") or [],
            "diff_summary": diff_summary,
            "source_warning": gh_evidence.get("source_warning"),
            "verified": gh_evidence.get("verified", False),
        }
        enriched.append(enriched_pr)

        _persist_pr_evidence(
            url=url,
            gh=gh_evidence,
            llm=llm_analysis,
            story=story,
            ticket_ctx=ticket_ctx,
            db=db,
        )

    return enriched, warnings


def _persist_pr_evidence(
    url: str,
    gh: dict,
    llm: "llm_service.LLMAnalysis | None",
    story: "Story",
    ticket_ctx: dict,
    db: "Session",
) -> None:
    """
    Persist a PREvidence record.  If a record for this URL already exists,
    update it (upsert by URL is intentionally simple for MVP).
    """
    from backend.models import PREvidence  # local import avoids circular at module level  # noqa: PLC0415

    # Resolve resolved_ticket_id from DB if possible
    resolved_ticket_id: str | None = None
    jira_key = ticket_ctx.get("jira_key")
    if jira_key:
        rt = db.query(ResolvedTicket).filter(ResolvedTicket.jira_key == jira_key).first()
        if rt:
            resolved_ticket_id = rt.id

    diff_summary = (llm.diff_summary if llm else None) or gh.get("diff_summary")
    code_analysis_notes = llm.code_analysis_notes if llm else None
    test_files_present = (
        llm.has_tests if (llm and llm.has_tests is not None)
        else gh.get("test_files_present")
    )

    existing = db.query(PREvidence).filter(PREvidence.url == url).first()
    if existing:
        existing.title = gh.get("title")
        existing.state = gh.get("state")
        existing.merged = gh.get("merged")
        existing.base_branch = gh.get("base_branch")
        existing.head_branch = gh.get("head_branch")
        existing.files_changed = gh.get("files_changed") or []
        existing.test_files_present = test_files_present
        existing.was_reverted = gh.get("was_reverted")
        existing.ci_checks = gh.get("ci_checks") or []
        existing.diff_summary = diff_summary
        existing.code_analysis_notes = code_analysis_notes
        existing.source_warning = gh.get("source_warning")
        existing.verified = gh.get("verified", False)
        db.add(existing)
    else:
        record = PREvidence(
            resolved_ticket_id=resolved_ticket_id,
            story_id=story.id,
            url=url,
            title=gh.get("title"),
            state=gh.get("state"),
            merged=gh.get("merged"),
            base_branch=gh.get("base_branch"),
            head_branch=gh.get("head_branch"),
            files_changed=gh.get("files_changed") or [],
            test_files_present=test_files_present,
            was_reverted=gh.get("was_reverted"),
            ci_checks=gh.get("ci_checks") or [],
            diff_summary=diff_summary,
            code_analysis_notes=code_analysis_notes,
            source=gh.get("source", "github_api"),
            source_warning=gh.get("source_warning"),
            verified=gh.get("verified", False),
        )
        db.add(record)

    db.commit()


# ---------------------------------------------------------------------------
# M4b — Outcome and BobSession evidence
# ---------------------------------------------------------------------------

def collect_outcome_evidence(
    similar_tickets_full: list[dict],
    db: "Session",
) -> tuple[list[dict], list[dict]]:
    """
    Fetch Outcome records for the Story records linked to similar resolved tickets.

    How: For each similar resolved ticket's jira_key, find the corresponding
    ResolvedTicket DB record.  ResolvedTickets do not have a direct FK to Story;
    instead we look for Story records with a matching jira_key.  When found,
    fetch their Outcome records.

    Returns (evidence_items, risk_items) using the standard evidence/risk shape.

    Signals (from plan):
      - ac_met=True (bool) or ac_met="successful" (str) → positive evidence
      - ac_met=False (bool) or ac_met="failed" (str) → risk item
      - ac_met="partial" → mild risk item
    No claim is made that AC were met due to merged PRs or passing CI.
    """
    evidence_items: list[dict] = []
    risk_items: list[dict] = []

    if not similar_tickets_full:
        return evidence_items, risk_items

    # Collect story_ids for all similar tickets' jira_keys
    jira_keys = [t.get("jira_key") for t in similar_tickets_full if t.get("jira_key")]
    story_ids: list[str] = []
    for key in jira_keys:
        story = db.query(Story).filter(Story.jira_key == key).first()
        if story:
            story_ids.append(story.id)

    if not story_ids:
        return evidence_items, risk_items

    outcomes = db.query(Outcome).filter(Outcome.story_id.in_(story_ids)).all()
    if not outcomes:
        return evidence_items, risk_items

    successes = [
        o for o in outcomes
        if o.ac_met is True or (isinstance(o.ac_met, str) and o.ac_met == "successful")
    ]
    failures = [
        o for o in outcomes
        if o.ac_met is False or (isinstance(o.ac_met, str) and o.ac_met == "failed")
    ]
    partials = [
        o for o in outcomes
        if isinstance(o.ac_met, str) and o.ac_met == "partial"
    ]

    if successes:
        evidence_items.append({
            "source": "outcome_records",
            "description": (
                f"{len(successes)} outcome record(s) for similar stories "
                "show acceptance criteria were met — positive historical signal. "
                "Note: this reflects recorded outcomes, not inferred from PR merge status."
            ),
            "verified": True,
        })

    if failures:
        risk_items.append({
            "description": (
                f"{len(failures)} outcome record(s) for similar stories "
                "show acceptance criteria were NOT met — historical risk signal."
            ),
            "severity": "high",
        })

    if partials:
        risk_items.append({
            "description": (
                f"{len(partials)} outcome record(s) for similar stories "
                "show partial acceptance criteria outcome — review scope carefully."
            ),
            "severity": "medium",
        })

    return evidence_items, risk_items


def collect_session_evidence(
    similar_tickets_full: list[dict],
    db: "Session",
) -> tuple[list[dict], list[dict]]:
    """
    Fetch BobSession records for Story records linked to similar resolved tickets.

    Returns (evidence_items, risk_items).

    Signals (from plan):
      - Total human_interventions count = 0 → positive evidence (bob-led signal)
      - Count 1–2 → collaborative signal (neutral, no item added)
      - Count ≥ 3 → risk item (human-led signal)
    """
    evidence_items: list[dict] = []
    risk_items: list[dict] = []

    if not similar_tickets_full:
        return evidence_items, risk_items

    jira_keys = [t.get("jira_key") for t in similar_tickets_full if t.get("jira_key")]
    story_ids: list[str] = []
    for key in jira_keys:
        story = db.query(Story).filter(Story.jira_key == key).first()
        if story:
            story_ids.append(story.id)

    if not story_ids:
        return evidence_items, risk_items

    sessions = db.query(BobSession).filter(BobSession.story_id.in_(story_ids)).all()
    if not sessions:
        return evidence_items, risk_items

    # Count total human interventions across all sessions for similar stories.
    # human_interventions is added in M4c; use getattr with fallback for compatibility.
    total_interventions = 0
    for session in sessions:
        interventions = getattr(session, "human_interventions", None)
        if isinstance(interventions, list):
            total_interventions += len(interventions)
        elif isinstance(interventions, int):
            total_interventions += interventions

    if total_interventions == 0:
        evidence_items.append({
            "source": "bob_sessions",
            "description": (
                f"{len(sessions)} Bob session(s) for similar stories "
                "recorded zero human interventions — positive bob-led signal."
            ),
            "verified": True,
        })
    elif total_interventions >= 3:
        risk_items.append({
            "description": (
                f"Bob sessions for similar stories recorded {total_interventions} "
                "human intervention(s) — suggests this type of work requires human oversight."
            ),
            "severity": "medium",
        })

    return evidence_items, risk_items


def build_code_analysis_notes(
    enriched_prs: list[dict],
    llm_unavailable_warning: str | None,
) -> str | None:
    """
    Build a prose code_analysis_notes string from enriched PR evidence.

    When LLM is available, the individual PR diff_summary fields provide
    the content.  When LLM is unavailable, a short pattern-based note is
    produced from file names.

    Returns None when no meaningful analysis is possible.
    """
    if not enriched_prs:
        return None

    # Collect LLM-generated notes
    notes: list[str] = []
    for pr in enriched_prs:
        if pr.get("diff_summary"):
            notes.append(f"PR {pr['url']}: {pr['diff_summary']}")

    if notes:
        return " | ".join(notes)

    # Fallback: pattern-based file analysis
    if llm_unavailable_warning:
        all_files: list[str] = []
        for pr in enriched_prs:
            all_files.extend(pr.get("files_changed") or [])
        if not all_files:
            return None
        test_files = [f for f in all_files if github_service._is_test_file(f)]
        unique_dirs = sorted({f.rsplit("/", 1)[0] for f in all_files if "/" in f})[:5]
        parts = [f"Files changed across similar PRs: {len(all_files)}."]
        if test_files:
            parts.append(f"Test files present: {len(test_files)}.")
        if unique_dirs:
            parts.append(f"Directories modified: {', '.join(unique_dirs)}.")
        parts.append("(LLM unavailable — pattern-based analysis only.)")
        return " ".join(parts)

    return None


# ---------------------------------------------------------------------------
# File selection for LLM context
# ---------------------------------------------------------------------------

# Maximum number of candidate files to fetch current source for
_MAX_FILES_FOR_LLM = 6
# Token-budget estimate: each char ≈ 0.25 tokens; budget ~4 000 tokens for source
_FILE_CONTENT_CHAR_BUDGET = 16_000


def select_files_for_llm(
    story: Story,
    similar_tickets: list[dict],
    enriched_prs: list[dict],
) -> list[dict]:
    """
    Rank candidate files from historical PR evidence by relevance to the current
    story and return up to _MAX_FILES_FOR_LLM entries for source fetching.

    Returns a list of dicts, each with:
        filename      : str  — file path as it appeared in the historical PR
        score         : float — composite relevance score (higher = more relevant)
        from_pr       : str  — URL of the PR this file came from
        base_branch   : str | None — PR base branch (preferred fetch ref)
        ac_met        : bool | None — whether the associated historical ticket's AC were met
        was_reverted  : bool | None — heuristic revert signal on the associated PR
        owner         : str | None — parsed from PR URL
        repo          : str | None — parsed from PR URL

    Ranking uses three signals (none is the final mode decision):
      1. Token overlap between file path tokens and current story text tokens.
         Frequent-but-uninformative files (appearing in every PR) are down-weighted
         by an IDF-style penalty so ubiquitous paths don't dominate.
      2. Whether the associated historical ticket has ac_met=True and was not
         subsequently flagged as reverted (was_reverted is not True).
      3. Whether the associated historical resolution was AI-led (mode_used="bob_led")
         and not subsequently reverted — a positive applicability signal.

    Files from PRs whose entire historical ticket was reverted receive a score
    penalty but are not excluded — the LLM should see them with context.

    Files are de-duplicated by filename; the highest-scoring occurrence wins.
    The returned list respects _MAX_FILES_FOR_LLM and is ordered score-descending.
    """
    if not enriched_prs:
        return []

    # Tokenise the current story for overlap scoring
    story_tokens: set[str] = set(_tokenise(_story_text(story)))

    # Build a lookup: pr_url → ticket metadata (for outcome signals)
    # similar_tickets carries was_reverted on the *ticket* level
    url_to_ticket: dict[str, dict] = {}
    for ticket in similar_tickets:
        for pr_url in ticket.get("linked_prs", []):
            if pr_url and pr_url not in url_to_ticket:
                url_to_ticket[pr_url] = ticket

    # Count how many PRs each filename appears in (for IDF-style penalty)
    filename_pr_count: Counter = Counter()
    for pr in enriched_prs:
        seen_in_pr: set[str] = set()
        for fname in pr.get("files_changed") or []:
            if fname and fname not in seen_in_pr:
                filename_pr_count[fname] += 1
                seen_in_pr.add(fname)

    total_prs = max(len(enriched_prs), 1)

    # Score every (filename, pr) pair
    best: dict[str, dict] = {}  # filename → best-scored candidate dict

    for pr in enriched_prs:
        pr_url = pr.get("url", "")
        ticket_ctx = url_to_ticket.get(pr_url, {})
        ac_met: bool | None = ticket_ctx.get("ac_met")
        mode_used: str | None = ticket_ctx.get("mode_used")
        ticket_reverted: bool | None = ticket_ctx.get("was_reverted")
        pr_reverted: bool | None = pr.get("was_reverted")

        # Parse owner/repo from URL for later fetching
        parsed = github_service.parse_pr_url(pr_url)
        owner: str | None = parsed[0] if parsed else None
        repo: str | None = parsed[1] if parsed else None
        base_branch: str | None = pr.get("base_branch")

        for fname in pr.get("files_changed") or []:
            if not isinstance(fname, str) or not fname:
                continue

            # ── Signal 1: token overlap (IDF-penalised) ──────────────────────
            file_tokens = set(_tokenise(fname.replace("/", " ").replace(".", " ")))
            overlap = len(story_tokens & file_tokens)
            # Files present in all PRs get a near-zero IDF weight
            idf_weight = math.log((1 + total_prs) / (1 + filename_pr_count[fname])) + 1.0
            token_score = overlap * idf_weight

            # ── Signal 2: outcome quality ─────────────────────────────────────
            # ac_met=True + not reverted → +1.5
            # ac_met=False → -0.5
            # ac_met=None → 0 (no signal either way)
            outcome_score = 0.0
            reverted = ticket_reverted is True or pr_reverted is True
            if ac_met is True and not reverted:
                outcome_score = 1.5
            elif ac_met is False:
                outcome_score = -0.5

            # ── Signal 3: AI-led success ──────────────────────────────────────
            # bob_led + ac_met + not reverted → +1.0 (positive applicability)
            ai_score = 0.0
            if mode_used == "bob_led" and ac_met is True and not reverted:
                ai_score = 1.0

            # Reverted tickets get a mild penalty so they appear later
            revert_penalty = -0.75 if reverted else 0.0

            composite = token_score + outcome_score + ai_score + revert_penalty

            if fname not in best or composite > best[fname]["score"]:
                best[fname] = {
                    "filename": fname,
                    "score": composite,
                    "from_pr": pr_url,
                    "base_branch": base_branch,
                    "ac_met": ac_met,
                    "was_reverted": ticket_reverted,
                    "owner": owner,
                    "repo": repo,
                }

    ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:_MAX_FILES_FOR_LLM]
