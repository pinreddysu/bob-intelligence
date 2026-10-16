"""
LLM analysis service — Milestone 4b / 4c.

Provides two public entry points:

  analyze_pr(...)
    Sends a single PR diff + story context to the configured LLM and returns
    a structured LLMAnalysis.  Used by historical_evidence_service during PR
    enrichment.

  analyze_ticket_readiness(...)
    Sends the new ticket's full context (description, AC, similar tickets with
    their resolutions and similarity scores, enriched PR metadata) to the LLM
    and asks it to assess semantic readiness across five dimensions:
      1. Whether the ticket provides enough information to implement the change.
      2. Whether missing reproduction steps / AC / environment genuinely block resolution.
      3. Whether historical fixes are relevant beyond textual similarity.
      4. What additional files, context, or evidence are needed.
      5. Whether each gap can be retrieved automatically or needs human input.

    Returns (ReadinessLLMAnalysis | None, warning_str | None).
    When LLM_API_KEY is absent or the call fails, returns (None, warning).

Provider selection (shared by both functions):
  LLM_PROVIDER env var: "watsonx" | "openai"
  LLM_API_KEY  env var: required for all providers.
  LLM_ENDPOINT env var: required for watsonx; optional for openai.

Design constraints (both functions):
  - The LLM does NOT score or rank stories.
  - LLM output is advisory only — it annotates deterministic check results.
  - Credentials, API access, file retrieval, and test execution are checked
    deterministically from actual results; the LLM cannot claim these are
    verified without evidence.
  - merged=True / passing CI is NOT forwarded to the LLM as proof of AC.
  - When the LLM JSON is malformed or missing required keys, a partial result
    is returned rather than raising.
  - Never invents file paths, PR content, or test outcomes.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LLMAnalysis:
    """
    Structured output from the LLM for a single PR analysis.

    All fields are optional/nullable — the LLM may return partial JSON or
    omit fields.  Callers must tolerate None for every field.
    """

    relevant: bool | None = None
    relevance_reason: str | None = None
    diff_summary: str | None = None
    has_tests: bool | None = None
    complexity: str | None = None          # "low" | "medium" | "high"
    risk_flags: list[str] = field(default_factory=list)
    intervention_signal: str | None = None  # "low" | "medium" | "high"
    mode_signal: str | None = None          # "bob_led" | "collaborative" | "human_led"
    mode_rationale: str | None = None
    code_analysis_notes: str | None = None
    # Warning recorded when the call partially succeeded (e.g. JSON parse error).
    source_warning: str | None = None


@dataclass
class ReadinessLLMAnalysis:
    """
    Structured output from the LLM for ticket-readiness semantic analysis.

    Covers five semantic dimensions assessed from ticket content + historical
    evidence.  All fields are nullable — callers must tolerate None.

    Design constraints:
      - sufficiency_verdict, blocking_gaps, evidence_relevance, needed_context,
        and auto_retrievable are all advisory.
      - The LLM is NOT asked whether credentials or API access work — those are
        checked deterministically by the caller from actual results.
      - The LLM is NOT asked whether tests passed or PRs were merged — those
        are known facts that the caller already holds.
    """

    # 1. Does the ticket provide enough information to implement the change?
    #    "sufficient" | "insufficient" | "partial"
    sufficiency_verdict: str | None = None
    # Short prose explanation of what is or is not sufficient.
    sufficiency_reason: str | None = None

    # 2. Do missing repro steps / AC / environment details genuinely block resolution?
    #    True when the LLM judges the missing context to be a hard blocker.
    context_blocks_resolution: bool | None = None
    # Which specific pieces of context are missing, per the LLM.
    blocking_gaps: list[str] = field(default_factory=list)

    # 3. Are historical fixes relevant beyond textual similarity?
    #    "strongly_relevant" | "partially_relevant" | "not_relevant" | "insufficient_evidence"
    evidence_relevance: str | None = None
    # One-sentence rationale for evidence_relevance.
    evidence_relevance_reason: str | None = None

    # 4. What additional files, context, or evidence are needed?
    needed_context: list[str] = field(default_factory=list)

    # 5. Can missing information be retrieved automatically, or does it need human input?
    #    True when the LLM assesses all gaps as auto-retrievable.
    auto_retrievable: bool | None = None
    # Per-gap retrievability annotations: list of {"item": str, "auto": bool, "reason": str}
    retrievability_notes: list[dict] = field(default_factory=list)

    # Recommended resolution mode from the LLM's semantic perspective.
    # "AI" | "AI + human" | "Human"
    recommended_mode: str | None = None
    # One-sentence rationale for recommended_mode.
    mode_rationale: str | None = None

    # Overall confidence in the assessment: "high" | "medium" | "low"
    confidence: str | None = None

    # Warning when the call partially succeeded (e.g. JSON parse error).
    source_warning: str | None = None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    story_title: str,
    story_description: str,
    story_ac: str,
    pr_title: str,
    pr_files: list[str],
    pr_merged: bool | None,
    pr_was_reverted: bool | None,
    resolved_ticket_title: str | None,
    resolved_ticket_mode: str | None,
    resolved_ticket_ac_met: bool | None,
) -> str:
    """Build the LLM prompt for PR analysis."""
    pr_merged_str = "yes" if pr_merged is True else ("no" if pr_merged is False else "unknown")
    reverted_str = "yes" if pr_was_reverted is True else ("no" if pr_was_reverted is False else "unknown")
    files_str = "\n".join(f"  - {f}" for f in (pr_files or [])[:40]) or "  (none available)"

    resolved_section = ""
    if resolved_ticket_title:
        ac_met_str = (
            "yes" if resolved_ticket_ac_met is True
            else ("no" if resolved_ticket_ac_met is False else "unknown")
        )
        resolved_section = f"""
RESOLVED TICKET (historical context — this was a similar past story):
  Title: {resolved_ticket_title}
  Mode used: {resolved_ticket_mode or "unknown"}
  AC met: {ac_met_str}
"""

    return f"""You are an engineering evidence analyst. Analyse the following GitHub PR in the context of a new story. Return ONLY valid JSON — no explanation outside the JSON block.

NEW STORY:
  Title: {story_title}
  Description: {story_description or "(none)"}
  Acceptance Criteria: {story_ac or "(none)"}
{resolved_section}
PR UNDER ANALYSIS:
  Title: {pr_title or "(none)"}
  Merged: {pr_merged_str}
  Title revert heuristic: {reverted_str} (pattern match only — does not confirm the PR was actually reverted)
  Files changed:
{files_str}

INSTRUCTIONS:
- "relevant": true if this PR addresses a similar concern to the new story; false otherwise.
- "relevance_reason": one sentence explaining why.
- "diff_summary": 1-2 sentences describing what code changed (based on file names and PR title only — do not hallucinate code you cannot see).
- "has_tests": true if any test file appears in the file list; false if none; null if uncertain.
- "complexity": "low", "medium", or "high" based on file count and domain signals.
- "risk_flags": list of short strings (empty list if none).
- "intervention_signal": "low", "medium", or "high" — estimated likelihood that a human would need to intervene.
- "mode_signal": "bob_led", "collaborative", or "human_led" — suggested execution mode signal from this PR.
- "mode_rationale": one sentence justifying mode_signal.
- "code_analysis_notes": 1-3 sentence prose summary suitable for a tech lead (null if nothing meaningful to say).

CRITICAL CONSTRAINTS:
- Do NOT claim AC were met because the PR was merged.
- Do NOT claim tests passed because CI was green.
- If you do not have enough information, use null or empty values — never invent facts.

Return ONLY this JSON schema (no other text):
{{
  "relevant": <bool>,
  "relevance_reason": "<string>",
  "diff_summary": "<string or null>",
  "has_tests": <bool or null>,
  "complexity": "<low|medium|high>",
  "risk_flags": [],
  "intervention_signal": "<low|medium|high>",
  "mode_signal": "<bob_led|collaborative|human_led>",
  "mode_rationale": "<string>",
  "code_analysis_notes": "<string or null>"
}}"""


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_openai(prompt: str, api_key: str, endpoint: str | None) -> tuple[str, str | None]:
    """
    Call OpenAI chat completions API.
    Returns (raw_content, error_message_or_None).
    """
    base = (endpoint or "https://api.openai.com").rstrip("/")
    url = f"{base}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 600,
    }
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
        if not resp.is_success:
            return "", f"OpenAI API returned HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, None
    except httpx.RequestError as exc:
        return "", f"Network error calling OpenAI API: {exc}"
    except (KeyError, IndexError) as exc:
        return "", f"Unexpected OpenAI response structure: {exc}"


def _call_watsonx(prompt: str, api_key: str, endpoint: str | None) -> tuple[str, str | None]:
    """
    Call IBM watsonx.ai text generation API.
    Returns (raw_content, error_message_or_None).
    """
    if not endpoint:
        return "", (
            "LLM_ENDPOINT is required for watsonx provider. "
            "Set LLM_ENDPOINT to your watsonx.ai inference URL."
        )
    base = endpoint.rstrip("/")
    # Support both the full inference URL and the base endpoint.
    if "/ml/v1/text/generation" not in base:
        url = f"{base}/ml/v1/text/generation?version=2023-05-29"
    else:
        url = base
    project_id = os.getenv("LLM_PROJECT_ID", "")
    model_id = os.getenv("LLM_MODEL", "ibm/granite-13b-chat-v2")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model_id": model_id,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 600,
            "temperature": 0,
        },
    }
    if project_id:
        body["project_id"] = project_id
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
        if not resp.is_success:
            return "", f"watsonx API returned HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        content = data["results"][0]["generated_text"]
        return content, None
    except httpx.RequestError as exc:
        return "", f"Network error calling watsonx API: {exc}"
    except (KeyError, IndexError) as exc:
        return "", f"Unexpected watsonx response structure: {exc}"


def _call_bob(prompt: str, api_key: str, endpoint: str | None) -> tuple[str, str | None]:
    """
    Call IBM Bob headless CLI for inference.

    Invokes: bob run --mode ask --format json --max-turns 3 <prompt>
    The prompt is passed as the positional argument; no stdin input is used.

    Required env vars:
      LLM_API_KEY  — Bob API key; passed as BOB_API_KEY to the subprocess.

    Response envelope expected from Bob:
      {"status": "success", "last_message": "<JSON string>"}

    Returns (last_message_string, error_or_None).
    The caller (_extract_json) handles parsing last_message as JSON.
    endpoint is accepted for interface compatibility but not used.
    """
    del endpoint  # not used; Bob CLI is invoked directly without an HTTP endpoint
    env = {**os.environ, "BOB_API_KEY": api_key}

    try:
        result = subprocess.run(
            ["bob", "run", "--mode", "ask", "--format", "json", "--max-turns", "3", prompt],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return "", "Bob CLI not found — ensure 'bob' is installed and on PATH."
    except subprocess.TimeoutExpired:
        return "", "Bob CLI timed out after 180 seconds."
    except OSError as exc:
        return "", f"Failed to launch Bob CLI: {exc}"

    if result.returncode != 0:
        stderr_snippet = result.stderr[:300] if result.stderr else "(no stderr)"
        return "", (
            f"Bob CLI exited with code {result.returncode}. "
            f"STDERR: {stderr_snippet!r}"
        )

    stdout = (result.stdout or "").strip()
    if not stdout:
        stderr_snippet = result.stderr[:300] if result.stderr else "(no stderr)"
        return "", (
            f"Bob CLI returned empty stdout. STDERR: {stderr_snippet!r}"
        )

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return "", (
            f"Bob CLI did not return valid JSON envelope. "
            f"STDOUT (truncated): {stdout[:300]!r}"
        )

    if not isinstance(envelope, dict):
        return "", f"Bob CLI envelope is not a JSON object: {type(envelope).__name__}."

    if envelope.get("status") != "success":
        return "", f"Bob CLI returned non-success status: {envelope.get('status')!r}."

    last_message = envelope.get("last_message")
    if not last_message:
        return "", f"Bob CLI envelope has no 'last_message' field: {list(envelope.keys())}."

    # last_message is itself a JSON string containing the structured output
    return last_message, None


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any] | None:
    """
    Extract the first JSON object from raw text (handles markdown code fences).
    Returns None if no valid JSON found.
    """
    raw = raw.strip()
    # Strip markdown code fence if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        raw = raw.strip()
    # Find the first { ... } block
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def analyze_pr(
    story_title: str,
    story_description: str | None,
    story_ac: str | None,
    pr_title: str | None,
    pr_files: list[str],
    pr_merged: bool | None,
    pr_was_reverted: bool | None,
    resolved_ticket_title: str | None = None,
    resolved_ticket_mode: str | None = None,
    resolved_ticket_ac_met: bool | None = None,
) -> tuple[LLMAnalysis | None, str | None]:
    """
    Call the configured LLM to analyse a PR in the context of a story.

    Returns (LLMAnalysis, source_warning).
      - When LLM_API_KEY is absent: (None, warning_string).
      - When the call fails:       (None, warning_string).
      - On success:                (LLMAnalysis, None or partial_warning).

    The caller must handle (None, warning) gracefully — pattern-matching
    fallbacks should be used when LLM is unavailable.

    IMPORTANT: The LLM output is advisory.  mode_signal does NOT override the
    deterministic mode_score; it is added to mode_evidence[] as an evidence item.
    """
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None, (
            "LLM analysis unavailable — LLM_API_KEY not configured. "
            "Set LLM_API_KEY and LLM_PROVIDER in .env to enable LLM PR analysis."
        )

    provider = os.getenv("LLM_PROVIDER", "bob").strip().lower()
    endpoint = os.getenv("LLM_ENDPOINT", "").strip() or None

    prompt = _build_prompt(
        story_title=story_title or "",
        story_description=story_description or "",
        story_ac=story_ac or "",
        pr_title=pr_title or "",
        pr_files=pr_files or [],
        pr_merged=pr_merged,
        pr_was_reverted=pr_was_reverted,
        resolved_ticket_title=resolved_ticket_title,
        resolved_ticket_mode=resolved_ticket_mode,
        resolved_ticket_ac_met=resolved_ticket_ac_met,
    )

    if provider == "watsonx":
        raw, error = _call_watsonx(prompt, api_key, endpoint)
    elif provider == "bob":
        raw, error = _call_bob(prompt, api_key, endpoint)
    else:
        raw, error = _call_openai(prompt, api_key, endpoint)

    if error:
        return None, f"LLM PR analysis failed: {error}"

    data = _extract_json(raw)
    if data is None:
        return None, f"LLM returned non-JSON response; skipping PR analysis. Raw: {raw[:200]!r}"

    # Build LLMAnalysis from parsed JSON — tolerate missing/null fields
    source_warning: str | None = None
    try:
        analysis = LLMAnalysis(
            relevant=data.get("relevant"),
            relevance_reason=data.get("relevance_reason"),
            diff_summary=data.get("diff_summary"),
            has_tests=data.get("has_tests"),
            complexity=data.get("complexity"),
            risk_flags=list(data.get("risk_flags") or []),
            intervention_signal=data.get("intervention_signal"),
            mode_signal=data.get("mode_signal"),
            mode_rationale=data.get("mode_rationale"),
            code_analysis_notes=data.get("code_analysis_notes"),
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"LLM response parsing error: {exc}"

    return analysis, source_warning


# ---------------------------------------------------------------------------
# Readiness prompt builder
# ---------------------------------------------------------------------------

def _build_readiness_prompt(
    story_title: str,
    story_description: str,
    story_ac: str,
    similar_tickets: list[dict],
    enriched_prs: list[dict],
) -> str:
    """Build the LLM prompt for ticket-readiness semantic analysis."""

    # Summarise similar tickets (up to 5, with key evidence fields)
    ticket_lines: list[str] = []
    for t in similar_tickets[:5]:
        ac_met_str = (
            "yes" if t.get("ac_met") is True
            else ("no" if t.get("ac_met") is False else "unknown")
        )
        reverted_str = "yes" if t.get("was_reverted") else "no"
        ticket_lines.append(
            f"  - {t.get('jira_key','?')} (score={t.get('similarity_score',0):.3f}): "
            f"title={t.get('title','?')!r}, resolution={t.get('resolution','unknown')!r}, "
            f"mode_used={t.get('mode_used','unknown')!r}, ac_met={ac_met_str}, reverted={reverted_str}"
        )
    tickets_str = "\n".join(ticket_lines) or "  (none)"

    # Summarise enriched PRs (up to 5, key fields only — no invented content)
    pr_lines: list[str] = []
    for pr in enriched_prs[:5]:
        files = pr.get("files_changed") or []
        files_preview = ", ".join(files[:5]) + ("..." if len(files) > 5 else "")
        test_str = (
            "yes" if pr.get("test_files_present") is True
            else ("no" if pr.get("test_files_present") is False else "unknown")
        )
        pr_lines.append(
            f"  - {pr.get('url','?')}: merged={pr.get('merged')}, "
            f"test_files={test_str}, files_changed=[{files_preview}], "
            f"diff_summary={pr.get('diff_summary') or '(unavailable)'!r}"
        )
    prs_str = "\n".join(pr_lines) or "  (none)"

    return f"""You are an engineering evidence analyst assessing whether a Jira ticket is ready for autonomous AI resolution.

NEW TICKET:
  Title: {story_title}
  Description: {story_description or "(none)"}
  Acceptance Criteria: {story_ac or "(none)"}

SIMILAR RESOLVED TICKETS (TF-IDF retrieval — similarity scores included):
{tickets_str}

LINKED PR EVIDENCE (GitHub metadata — file names only, no diff content):
{prs_str}

INSTRUCTIONS — assess the following five dimensions:

1. SUFFICIENCY: Does the ticket provide enough information to understand and implement the change?
   - "sufficient": clear problem, expected behaviour, and done condition are stated.
   - "partial": some information is present but key details are missing.
   - "insufficient": the ticket is too vague or short to act on.

2. BLOCKING GAPS: Do any missing pieces (reproduction steps, acceptance criteria, environment) genuinely block resolution, or can they be reasonably inferred from the description?
   - List only gaps that materially affect the ability to implement and verify the fix.
   - Leave "blocking_gaps" empty if nothing is genuinely blocking.

3. EVIDENCE RELEVANCE: Are the historical tickets relevant beyond textual similarity?
   - "strongly_relevant": historical fixes address the same root cause and the proposed approach applies to the current ticket.
   - "partially_relevant": historical tickets share domain/area but resolution may not directly apply.
   - "not_relevant": similar words, different problem — historical evidence does not support the fix.
   - "insufficient_evidence": too few similar tickets to assess.

4. NEEDED CONTEXT: What additional files, context, or evidence would materially improve confidence?
   - Be specific (e.g. "controller handling the /login route", "current test suite for UserAuthService").
   - Leave empty if nothing material is missing.

5. RETRIEVABILITY: For each item in "needed_context", state whether it can be retrieved automatically (e.g. from the repo via GitHub API) or requires human input.

Also provide:
  - "recommended_mode": "AI", "AI + human", or "Human" based purely on the semantic evidence above.
  - "mode_rationale": one sentence justifying recommended_mode.
  - "confidence": "high", "medium", or "low" — your confidence in this assessment.

CRITICAL CONSTRAINTS:
- Do NOT claim credentials, tokens, or API access are working — those are checked separately.
- Do NOT claim tests passed or PRs were merged as proof of AC.
- Do NOT invent file paths, code, or test outcomes.
- If you do not have enough information for a field, use null or an empty list.

Return ONLY this JSON (no other text):
{{
  "sufficiency_verdict": "<sufficient|partial|insufficient>",
  "sufficiency_reason": "<string>",
  "context_blocks_resolution": <bool>,
  "blocking_gaps": ["<string>", ...],
  "evidence_relevance": "<strongly_relevant|partially_relevant|not_relevant|insufficient_evidence>",
  "evidence_relevance_reason": "<string>",
  "needed_context": ["<string>", ...],
  "auto_retrievable": <bool>,
  "retrievability_notes": [{{"item": "<string>", "auto": <bool>, "reason": "<string>"}}],
  "recommended_mode": "<AI|AI + human|Human>",
  "mode_rationale": "<string>",
  "confidence": "<high|medium|low>"
}}"""


def analyze_ticket_readiness(
    story_title: str,
    story_description: str | None,
    story_ac: str | None,
    similar_tickets: list[dict],
    enriched_prs: list[dict],
) -> tuple[ReadinessLLMAnalysis | None, str | None]:
    """
    Call the configured LLM to assess ticket readiness semantically.

    Parameters
    ----------
    story_title       : ticket title
    story_description : ticket description text
    story_ac          : acceptance criteria text
    similar_tickets   : output of historical_evidence_service.find_similar()
    enriched_prs      : output of historical_evidence_service.enrich_prs_with_github()

    Returns
    -------
    (ReadinessLLMAnalysis, warning) where:
      - When LLM_API_KEY is absent: (None, warning_string)
      - When the call fails:        (None, warning_string)
      - On success:                 (ReadinessLLMAnalysis, None or partial_warning)

    The caller must handle (None, warning) gracefully — deterministic fallbacks
    take over when LLM is unavailable.

    The LLM output is advisory — it annotates the deterministic check results
    produced by ticket_readiness_service but does not override them.
    Credentials, file access, and test execution are NOT assessed by the LLM.
    """
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None, (
            "LLM readiness analysis unavailable — LLM_API_KEY not configured. "
            "Set LLM_API_KEY and LLM_PROVIDER in .env to enable semantic ticket analysis."
        )

    provider = os.getenv("LLM_PROVIDER", "bob").strip().lower()
    endpoint = os.getenv("LLM_ENDPOINT", "").strip() or None

    prompt = _build_readiness_prompt(
        story_title=story_title or "",
        story_description=story_description or "",
        story_ac=story_ac or "",
        similar_tickets=similar_tickets or [],
        enriched_prs=enriched_prs or [],
    )

    if provider == "watsonx":
        raw, error = _call_watsonx(prompt, api_key, endpoint)
    elif provider == "bob":
        raw, error = _call_bob(prompt, api_key, endpoint)
    else:
        raw, error = _call_openai(prompt, api_key, endpoint)

    if error:
        return None, f"LLM ticket-readiness analysis failed: {error}"

    data = _extract_json(raw)
    if data is None:
        return None, (
            f"LLM returned non-JSON response for readiness analysis; "
            f"skipping semantic check. Raw: {raw[:200]!r}"
        )

    source_warning: str | None = None
    try:
        analysis = ReadinessLLMAnalysis(
            sufficiency_verdict=data.get("sufficiency_verdict"),
            sufficiency_reason=data.get("sufficiency_reason"),
            context_blocks_resolution=data.get("context_blocks_resolution"),
            blocking_gaps=list(data.get("blocking_gaps") or []),
            evidence_relevance=data.get("evidence_relevance"),
            evidence_relevance_reason=data.get("evidence_relevance_reason"),
            needed_context=list(data.get("needed_context") or []),
            auto_retrievable=data.get("auto_retrievable"),
            retrievability_notes=list(data.get("retrievability_notes") or []),
            recommended_mode=data.get("recommended_mode"),
            mode_rationale=data.get("mode_rationale"),
            confidence=data.get("confidence"),
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"LLM readiness response parsing error: {exc}"

    return analysis, source_warning


# ---------------------------------------------------------------------------
# Mode recommendation dataclass
# ---------------------------------------------------------------------------

_VALID_MODES = frozenset({"bob_led", "collaborative", "human_led"})


@dataclass
class ModeAnalysis:
    """
    Structured output from analyze_mode().

    mode       : "bob_led" | "collaborative" | "human_led"
    rationale  : concise evidence-based explanation
    warning    : uncertainty or service-availability note (None when absent)
    llm_used   : True when the mode came from the LLM; False for the fallback
    """
    mode: str
    rationale: str
    warning: str | None = None
    llm_used: bool = True


# ---------------------------------------------------------------------------
# Mode prompt builder
# ---------------------------------------------------------------------------

def _build_mode_prompt(
    story_title: str,
    story_description: str,
    story_ac: str,
    story_blockers: list[str],
    similar_tickets: list[dict],
    enriched_prs: list[dict],
    current_files: list[dict],
) -> str:
    """Build the LLM prompt for evidence-based mode recommendation."""

    # Similar tickets (up to 5)
    ticket_lines: list[str] = []
    for t in similar_tickets[:5]:
        ac_str = "yes" if t.get("ac_met") is True else ("no" if t.get("ac_met") is False else "unknown")
        rev_str = "yes (heuristic only)" if t.get("was_reverted") else "no"
        ticket_lines.append(
            f"  - {t.get('jira_key','?')} (similarity={t.get('similarity_score',0):.3f}): "
            f"title={t.get('title','?')!r}, mode_used={t.get('mode_used') or 'unknown'}, "
            f"ac_met={ac_str}, was_reverted={rev_str}, resolution={t.get('resolution') or 'unknown'}"
        )
    tickets_str = "\n".join(ticket_lines) or "  (none)"

    # Enriched PRs (up to 5) — patches included when present
    pr_lines: list[str] = []
    for pr in enriched_prs[:5]:
        files = pr.get("files_changed") or []
        files_preview = ", ".join(files[:5]) + ("..." if len(files) > 5 else "")
        test_str = (
            "yes" if pr.get("test_files_present") is True
            else ("no" if pr.get("test_files_present") is False else "unknown")
        )
        rev_str = (
            "yes (title heuristic only)" if pr.get("was_reverted") is True
            else ("no" if pr.get("was_reverted") is False else "unknown")
        )
        pr_lines.append(
            f"  - {pr.get('url','?')}: base_branch={pr.get('base_branch') or 'unknown'}, "
            f"merged={pr.get('merged')}, test_files={test_str}, "
            f"title_revert_heuristic={rev_str}, files=[{files_preview}]"
        )
        patches = pr.get("patches") or []
        for p in patches[:3]:
            fname = p.get("filename", "?")
            patch_text = (p.get("patch") or "")[:400]
            pr_lines.append(f"    patch:{fname}:\n{patch_text}")
    prs_str = "\n".join(pr_lines) or "  (none)"

    # Current source excerpts
    src_lines: list[str] = []
    for cf in current_files:
        fname = cf.get("filename", "?")
        ref = cf.get("ref", "unknown ref")
        excerpt = (cf.get("content") or "")[:600]
        warning = cf.get("warning")
        src_lines.append(
            f"  - {fname} (ref: {ref})"
            + (f" [WARNING: {warning}]" if warning else "")
            + (f"\n{excerpt}" if excerpt else "\n    (content unavailable)")
        )
    src_str = "\n".join(src_lines) or "  (none — source context unavailable)"

    blockers_str = ", ".join(str(b) for b in story_blockers) if story_blockers else "none"

    return f"""You are an engineering evidence analyst recommending an execution mode for a software ticket.
Return ONLY valid JSON — no explanation outside the JSON block.

CURRENT TICKET:
  Title: {story_title}
  Description: {story_description or "(none)"}
  Acceptance Criteria: {story_ac or "(none)"}
  Blockers: {blockers_str}

SIMILAR RESOLVED TICKETS (retrieved by TF-IDF — similarity scores are retrieval signals, not mode decisions):
{tickets_str}

LINKED PR EVIDENCE (file names, patches, and metadata from historical PRs):
{prs_str}

CURRENT SOURCE EXCERPTS (fetched at the ref shown — empty means unavailable, not that the file is empty):
{src_str}

INSTRUCTIONS:
Recommend one of three execution modes based solely on the evidence above:
  "bob_led"      — Strong, applicable historical evidence; clear implementation target;
                   relevant current source context; feasible validation path; manageable risk.
  "collaborative" — Useful evidence exists but adaptation, uncertainty, missing context,
                   or human review is warranted.
  "human_led"    — Evidence insufficient or conflicting; implementation target unclear;
                   risk too high for autonomous work.

CRITICAL CONSTRAINTS:
- Do NOT base the mode on description length, keyword presence, or TF-IDF score thresholds.
- Do NOT claim tests passed or AC were met because a PR was merged or CI was green.
- Do NOT treat "title_revert_heuristic=yes" as a confirmed revert — it is a title pattern only.
- Do NOT claim current source was inspected unless an excerpt is shown above.
- If evidence is missing, conflicting, or unavailable, reflect that in "rationale".
- If blockers are present, factor them into the mode decision.
- "warning" must be non-null when evidence is absent, conflicting, or service gaps exist.

Return ONLY this JSON (no other text):
{{
  "mode": "<bob_led|collaborative|human_led>",
  "rationale": "<concise evidence-based explanation, 2-4 sentences>",
  "warning": "<uncertainty or service-availability note, or null>"
}}"""


# ---------------------------------------------------------------------------
# Public: evidence-based mode recommendation
# ---------------------------------------------------------------------------

def analyze_mode(
    story_title: str,
    story_description: str | None,
    story_ac: str | None,
    story_blockers: list[str],
    similar_tickets: list[dict],
    enriched_prs: list[dict],
    current_files: list[dict],
) -> ModeAnalysis:
    """
    Call the configured LLM to recommend an execution mode from evidence.

    Parameters
    ----------
    story_title       : ticket title
    story_description : ticket description
    story_ac          : acceptance criteria text
    story_blockers    : list of blocking issue keys
    similar_tickets   : output of historical_evidence_service.find_similar()
    enriched_prs      : output of historical_evidence_service.enrich_prs_with_github()
                        including transient "patches" dicts
    current_files     : list of dicts {filename, ref, content, warning} produced by
                        the caller after fetching via github_service.fetch_file_content()

    Returns
    -------
    ModeAnalysis — never raises.
      llm_used=False when LLM is unavailable or the call fails; in that case
      mode="collaborative" with warning explicitly labelled as NOT evidence-based.

    Mode decision criteria
    ----------------------
    bob_led      : strong applicable evidence, clear target, source context, low risk
    collaborative: useful evidence with uncertainty, adaptation needed, or human review warranted
    human_led    : insufficient/conflicting evidence, unclear target, or high risk

    The LLM must not determine mode from description length, keyword patterns,
    presence of Given/When/Then, or TF-IDF score thresholds.
    """
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return ModeAnalysis(
            mode="collaborative",
            rationale=(
                "LLM analysis unavailable — LLM_API_KEY not configured. "
                "Mode defaulted to 'collaborative' as a conservative fallback."
            ),
            warning=(
                "NOT an evidence-based recommendation. "
                "LLM_API_KEY is not configured; set it in .env to enable mode analysis. "
                "Evidence retrieved: "
                f"{len(similar_tickets)} similar ticket(s), "
                f"{len(enriched_prs)} enriched PR(s), "
                f"{len(current_files)} source file(s)."
            ),
            llm_used=False,
        )

    provider = os.getenv("LLM_PROVIDER", "bob").strip().lower()
    endpoint = os.getenv("LLM_ENDPOINT", "").strip() or None

    prompt = _build_mode_prompt(
        story_title=story_title or "",
        story_description=story_description or "",
        story_ac=story_ac or "",
        story_blockers=list(story_blockers or []),
        similar_tickets=similar_tickets or [],
        enriched_prs=enriched_prs or [],
        current_files=current_files or [],
    )

    if provider == "watsonx":
        raw, error = _call_watsonx(prompt, api_key, endpoint)
    elif provider == "bob":
        raw, error = _call_bob(prompt, api_key, endpoint)
    else:
        raw, error = _call_openai(prompt, api_key, endpoint)

    if error:
        return ModeAnalysis(
            mode="collaborative",
            rationale=(
                "LLM mode analysis failed; mode defaulted to 'collaborative' as a "
                "conservative fallback."
            ),
            warning=(
                f"NOT an evidence-based recommendation. LLM call failed: {error}. "
                "Evidence retrieved: "
                f"{len(similar_tickets)} similar ticket(s), "
                f"{len(enriched_prs)} enriched PR(s), "
                f"{len(current_files)} source file(s)."
            ),
            llm_used=False,
        )

    data = _extract_json(raw)
    if data is None:
        return ModeAnalysis(
            mode="collaborative",
            rationale=(
                "LLM returned a non-JSON response; mode defaulted to 'collaborative'."
            ),
            warning=(
                f"NOT an evidence-based recommendation. "
                f"LLM returned malformed output. Raw (truncated): {raw[:200]!r}"
            ),
            llm_used=False,
        )

    # Validate and extract fields
    raw_mode = data.get("mode")
    if raw_mode not in _VALID_MODES:
        return ModeAnalysis(
            mode="collaborative",
            rationale=(
                "LLM returned an unrecognised mode value; defaulted to 'collaborative'."
            ),
            warning=(
                f"NOT an evidence-based recommendation. "
                f"LLM returned invalid mode {raw_mode!r}; expected one of {sorted(_VALID_MODES)}."
            ),
            llm_used=False,
        )

    rationale = data.get("rationale") or ""
    if not isinstance(rationale, str):
        rationale = str(rationale)

    llm_warning = data.get("warning")
    if llm_warning is not None and not isinstance(llm_warning, str):
        llm_warning = str(llm_warning)

    return ModeAnalysis(
        mode=raw_mode,
        rationale=rationale,
        warning=llm_warning or None,
        llm_used=True,
    )
