"""
Historical evidence service — Milestone 4a.

Responsibilities:
  1. find_similar(story, db)  — TF-IDF cosine similarity between the new story
     and every ResolvedTicket in the database; returns up to 5 tickets with
     similarity_score ≥ 0.25, ordered by score descending.
  2. build_supporting_prs(resolved_tickets) — collect the union of linked_prs
     from the matched resolved tickets (de-duplicated by URL).
  3. compute_evidence_confidence(similar_tickets) — "high" / "medium" / "low" / "none"
     based on how many similar tickets have outcome signals (mode_used + ac_met).

Design constraints (from plan):
  - story_points MUST NOT influence any output.
  - No external API keys required for M4a (pure TF-IDF, in-process).
  - The find_similar() interface is intentionally thin so the backend can be
    swapped to embeddings in a later milestone without touching recommendation_service.
  - When the resolved ticket corpus is empty, find_similar returns [] immediately
    (no error, no fallback to invented data).
  - PR URLs are taken verbatim from resolved ticket records; GitHub enrichment
    is deferred to M4b.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from backend.models import ResolvedTicket, Story


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

_SIMILARITY_THRESHOLD = 0.25
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

    Each PR URL becomes a dict with:
        url, merged (null — GitHub enrichment deferred to M4b),
        files_changed ([] — deferred), title (null — deferred)

    De-duplicated by URL. Order preserved (first occurrence wins).
    """
    seen: set[str] = set()
    result: list[dict] = []
    for ticket in similar_tickets:
        for pr_url in ticket.get("linked_prs", []):
            if pr_url and pr_url not in seen:
                seen.add(pr_url)
                result.append({
                    "url": pr_url,
                    "merged": None,       # GitHub enrichment in M4b
                    "files_changed": [],  # GitHub enrichment in M4b
                    "title": None,        # GitHub enrichment in M4b
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
