"""
Jira service — Milestone 2.

Responsibilities:
  1. Fetch a story from the Jira REST API v3 (when credentials are configured).
  2. Load pre-baked sample stories / developer profiles from JSON files.
  3. Return structured result dicts used by the /api/stories router.

Explicit behaviour contract (no silent substitution):
  - When JIRA credentials are absent:   source_status="credentials_missing"
  - When the Jira API returns an error:  source_status="jira_error"
  - When import_source="sample":         source_status="sample_import"
  - Sample data is NEVER silently substituted for a failed Jira import.

Custom-field validation:
  - JIRA_STORY_POINTS_FIELD and JIRA_AC_FIELD are read from env.
  - The service validates that the configured field keys are present in the
    Jira response rather than assuming hardcoded values.
  - Missing / incorrect fields produce a source_warning, not a silent null.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"
_SAMPLE_STORIES_PATH = _SAMPLE_DIR / "stories.json"
_SAMPLE_DEV_PROFILES_PATH = _SAMPLE_DIR / "developer_profiles.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _jira_credentials() -> tuple[str, str, str] | None:
    """Return (base_url, email, token) or None if any credential is missing."""
    base_url = os.getenv("JIRA_BASE_URL", "").strip()
    email = os.getenv("JIRA_USER_EMAIL", "").strip()
    token = os.getenv("JIRA_API_TOKEN", "").strip()
    if not (base_url and email and token):
        return None
    return base_url, email, token


def _story_points_field() -> str:
    """Return the configured story-points custom field key (default: customfield_10016)."""
    return os.getenv("JIRA_STORY_POINTS_FIELD", "customfield_10016").strip()


def _ac_field() -> str | None:
    """Return the configured acceptance-criteria field key, or None if not set."""
    val = os.getenv("JIRA_AC_FIELD", "").strip()
    return val if val else None


# ---------------------------------------------------------------------------
# Jira REST API v3 fetch
# ---------------------------------------------------------------------------

def fetch_from_jira(jira_key: str) -> dict[str, Any]:
    """
    Fetch a single story from the Jira REST API v3.

    Returns a dict with keys:
        story_data:      dict of normalised story fields (or None on error)
        source_status:   "jira" | "credentials_missing" | "jira_error"
        source_warning:  human-readable warning string (or None on success)
    """
    creds = _jira_credentials()
    if creds is None:
        return {
            "story_data": None,
            "source_status": "credentials_missing",
            "source_warning": (
                "Jira credentials are not configured. "
                "Set JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN in .env "
                "to enable live Jira import."
            ),
        }

    base_url, email, token = creds
    sp_field = _story_points_field()
    ac_field = _ac_field()

    url = f"{base_url}/rest/api/3/issue/{jira_key}?expand=names"

    try:
        resp = httpx.get(
            url,
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        return {
            "story_data": None,
            "source_status": "jira_error",
            "source_warning": (
                f"Jira returned HTTP {status_code} for issue {jira_key}. "
                "Check that the issue key is correct and your credentials have read access."
            ),
        }
    except httpx.RequestError as exc:
        return {
            "story_data": None,
            "source_status": "jira_error",
            "source_warning": (
                f"Network error contacting Jira: {exc}. "
                "Check JIRA_BASE_URL and network connectivity."
            ),
        }

    raw = resp.json()
    fields = raw.get("fields", {})

    # ── Field validation ───────────────────────────────────────────────────
    warnings: list[str] = []

    # Validate story-points field
    story_points: int | None = None
    if sp_field in fields:
        sp_value = fields[sp_field]
        if sp_value is not None:
            try:
                story_points = int(sp_value)
            except (TypeError, ValueError):
                warnings.append(
                    f"Story-points field '{sp_field}' has unexpected value '{sp_value}' — stored as null."
                )
    else:
        warnings.append(
            f"Story-points field '{sp_field}' not present in Jira response. "
            "Verify JIRA_STORY_POINTS_FIELD in .env by calling "
            f"GET /rest/api/3/issue/{jira_key}?expand=names."
        )

    # Validate acceptance-criteria field
    acceptance_criteria: str | None = None
    if ac_field:
        if ac_field in fields:
            ac_value = fields[ac_field]
            if isinstance(ac_value, str):
                acceptance_criteria = ac_value or None
            elif isinstance(ac_value, dict):
                # Atlassian Document Format — extract plain text
                acceptance_criteria = _extract_adf_text(ac_value) or None
            else:
                warnings.append(
                    f"Acceptance-criteria field '{ac_field}' has an unexpected format "
                    f"(type: {type(ac_value).__name__}) — stored as null."
                )
        else:
            warnings.append(
                f"Acceptance-criteria field '{ac_field}' not present in Jira response. "
                "Verify JIRA_AC_FIELD in .env."
            )
    else:
        warnings.append(
            "JIRA_AC_FIELD is not configured — acceptance criteria will not be imported. "
            "Set JIRA_AC_FIELD in .env after inspecting the Jira response fields."
        )

    # ── Core fields ────────────────────────────────────────────────────────
    priority_name = (fields.get("priority") or {}).get("name", "").lower() or None
    status_name = (fields.get("status") or {}).get("name") or None
    assignee_display = ((fields.get("assignee") or {}).get("displayName") or None)

    labels = fields.get("labels") or []

    # Blockers: issues that block this ticket
    blockers: list[str] = []
    for link in fields.get("issuelinks") or []:
        link_type = (link.get("type") or {}).get("inward", "")
        if "block" in link_type.lower() and "inwardIssue" in link:
            blocker_key = (link["inwardIssue"] or {}).get("key")
            if blocker_key:
                blockers.append(blocker_key)

    # Linked PRs from remote links (requires separate call — stored as empty here;
    # full implementation in Milestone 4 when git evidence is wired up).
    linked_prs: list[str] = []

    story_data = {
        "jira_key": jira_key,
        "title": fields.get("summary") or jira_key,
        "description": _extract_description(fields.get("description")),
        "acceptance_criteria": acceptance_criteria,
        "story_points": story_points,
        "labels": labels,
        "priority": priority_name,
        "status": status_name,
        "assignee": assignee_display,
        "blockers": blockers,
        "linked_prs": linked_prs,
        "source": "jira",
    }

    source_warning = "  |  ".join(warnings) if warnings else None

    return {
        "story_data": story_data,
        "source_status": "jira",
        "source_warning": source_warning,
    }


# ---------------------------------------------------------------------------
# Sample data import
# ---------------------------------------------------------------------------

def load_sample_stories() -> list[dict[str, Any]]:
    """
    Return all sample stories from the JSON file.
    Each story is tagged source='sample'.  The _comment key is stripped.
    """
    raw = _load_json(_SAMPLE_STORIES_PATH)
    result = []
    for entry in raw:
        story = {k: v for k, v in entry.items() if not k.startswith("_")}
        story["source"] = "sample"  # enforce even if JSON value differs
        result.append(story)
    return result


def load_sample_developer_profiles() -> list[dict[str, Any]]:
    """
    Return all sample developer profiles from the JSON file.
    Each profile is tagged source='sample'.  The _comment key is stripped.
    """
    raw = _load_json(_SAMPLE_DEV_PROFILES_PATH)
    result = []
    for entry in raw:
        profile = {k: v for k, v in entry.items() if not k.startswith("_")}
        profile["source"] = "sample"  # enforce even if JSON value differs
        result.append(profile)
    return result


# ---------------------------------------------------------------------------
# ADF / description helpers
# ---------------------------------------------------------------------------

def _extract_description(description_field: Any) -> str | None:
    """Extract plain text from a Jira description (ADF or plain string)."""
    if description_field is None:
        return None
    if isinstance(description_field, str):
        return description_field or None
    if isinstance(description_field, dict):
        return _extract_adf_text(description_field) or None
    return None


def _extract_adf_text(node: dict) -> str:
    """
    Recursively extract plain text from an Atlassian Document Format node.
    Preserves newlines between block nodes for readability.
    """
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type", "")
    if node_type == "text":
        return node.get("text", "")

    parts: list[str] = []
    for child in node.get("content") or []:
        parts.append(_extract_adf_text(child))

    separator = "\n" if node_type in ("paragraph", "heading", "listItem", "bulletList", "orderedList") else ""
    return separator.join(p for p in parts if p)
