"""
/api/resolved-tickets router — Milestone 4a.

Endpoints:
  POST /api/resolved-tickets/import   Import resolved tickets (sample or Jira).
  GET  /api/resolved-tickets          List all resolved tickets.

Import rules:
  - source="sample": loads from sample_data/resolved_tickets.json.
    Records are labeled source="sample". Import is idempotent — duplicates
    are skipped by jira_key (no error, counted in skipped_duplicates).
  - source="jira":  calls Jira search API with configured JQL.
    When credentials are absent, returns source_status="credentials_missing".
    When Jira API returns an error, returns source_status="jira_error".
    Sample data is NEVER silently substituted for a failed Jira import.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ResolvedTicket
from backend.schemas import (
    ResolvedTicketImportRequest,
    ResolvedTicketImportResponse,
    ResolvedTicketListResponse,
    ResolvedTicketResponse,
)

router = APIRouter(prefix="/api/resolved-tickets", tags=["resolved-tickets"])

_SAMPLE_PATH = Path(__file__).parent.parent / "sample_data" / "resolved_tickets.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_sample() -> list[dict]:
    with open(_SAMPLE_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [{k: v for k, v in entry.items() if not k.startswith("_")} for entry in raw]


def _jira_credentials() -> tuple[str, str, str] | None:
    base_url = os.getenv("JIRA_BASE_URL", "").strip()
    email = os.getenv("JIRA_USER_EMAIL", "").strip()
    token = os.getenv("JIRA_API_TOKEN", "").strip()
    if not (base_url and email and token):
        return None
    return base_url, email, token


def _jira_resolved_jql() -> str:
    return os.getenv(
        "JIRA_RESOLVED_JQL",
        "project=PIE AND status=Done ORDER BY updated DESC",
    ).strip()


def _fetch_from_jira() -> dict:
    """
    Fetch resolved tickets from Jira using the configured JQL.

    Returns dict with keys: tickets (list[dict]), source_status, source_warning.
    """
    creds = _jira_credentials()
    if creds is None:
        return {
            "tickets": [],
            "source_status": "credentials_missing",
            "source_warning": (
                "Jira credentials are not configured. "
                "Set JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN in .env "
                "to enable live Jira resolved-ticket import."
            ),
        }

    base_url, email, token = creds
    jql = _jira_resolved_jql()
    url = f"{base_url}/rest/api/3/search"

    try:
        resp = httpx.get(
            url,
            auth=(email, token),
            headers={"Accept": "application/json"},
            params={"jql": jql, "maxResults": 50, "fields": "summary,description,resolution,labels,issuelinks,status"},
            timeout=20.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return {
            "tickets": [],
            "source_status": "jira_error",
            "source_warning": (
                f"Jira returned HTTP {exc.response.status_code} for JQL '{jql}'. "
                "Check credentials and project permissions."
            ),
        }
    except httpx.RequestError as exc:
        return {
            "tickets": [],
            "source_status": "jira_error",
            "source_warning": (
                f"Network error contacting Jira: {exc}. "
                "Check JIRA_BASE_URL and network connectivity."
            ),
        }

    issues = resp.json().get("issues", [])
    tickets: list[dict] = []
    for issue in issues:
        fields = issue.get("fields", {})
        resolution_obj = fields.get("resolution") or {}
        resolution = resolution_obj.get("name") or None

        # Extract description (ADF or plain text)
        desc_field = fields.get("description")
        description: str | None = None
        if isinstance(desc_field, str):
            description = desc_field or None
        elif isinstance(desc_field, dict):
            description = _extract_adf_text(desc_field) or None

        tickets.append({
            "jira_key": issue.get("key"),
            "title": fields.get("summary") or issue.get("key"),
            "description": description,
            "resolution": resolution,
            "labels": fields.get("labels") or [],
            "linked_prs": [],      # GitHub PR links require separate enrichment (M4b)
            "files_changed": [],   # Populated in M4b
            "mode_used": None,     # Populated from Outcome records in M5b
            "ac_met": None,        # Populated from Outcome records in M5b
            "was_reverted": False,
            "source": "jira",
        })

    return {
        "tickets": tickets,
        "source_status": "jira",
        "source_warning": None,
    }


def _extract_adf_text(node: dict) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_extract_adf_text(child) for child in (node.get("content") or [])]
    sep = "\n" if node.get("type") in ("paragraph", "heading", "listItem", "bulletList", "orderedList") else ""
    return sep.join(p for p in parts if p)


def _upsert_tickets(
    ticket_dicts: list[dict],
    db: Session,
) -> tuple[list[ResolvedTicket], int]:
    """
    Insert tickets that don't already exist (keyed by jira_key).
    Returns (inserted_records, skipped_count).
    """
    inserted: list[ResolvedTicket] = []
    skipped = 0

    for data in ticket_dicts:
        jira_key = data.get("jira_key")
        if not jira_key:
            continue
        existing = db.query(ResolvedTicket).filter(ResolvedTicket.jira_key == jira_key).first()
        if existing:
            skipped += 1
            continue

        record = ResolvedTicket(
            jira_key=jira_key,
            title=data.get("title") or jira_key,
            description=data.get("description"),
            resolution=data.get("resolution"),
            labels=data.get("labels") or [],
            linked_prs=data.get("linked_prs") or [],
            files_changed=data.get("files_changed") or [],
            mode_used=data.get("mode_used"),
            ac_met=data.get("ac_met"),
            was_reverted=bool(data.get("was_reverted", False)),
            source=data.get("source", "sample"),
        )
        db.add(record)
        inserted.append(record)

    if inserted:
        db.commit()
        for r in inserted:
            db.refresh(r)

    return inserted, skipped


# ---------------------------------------------------------------------------
# POST /api/resolved-tickets/import
# ---------------------------------------------------------------------------

@router.post("/import", response_model=ResolvedTicketImportResponse, status_code=201)
def import_resolved_tickets(
    body: ResolvedTicketImportRequest,
    db: Session = Depends(get_db),
) -> ResolvedTicketImportResponse:
    """
    Import resolved tickets from sample data or live Jira.

    - source="sample": always succeeds; records labeled source="sample".
    - source="jira":   requires JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN.
      Returns source_status="credentials_missing" when any credential is absent.
      Returns source_status="jira_error" on HTTP or network errors.
      Sample data is NEVER substituted for a failed Jira call.
    """
    if body.source == "sample":
        raw_tickets = _load_sample()
        for t in raw_tickets:
            t["source"] = "sample"  # enforce even if JSON value differs
        inserted, skipped = _upsert_tickets(raw_tickets, db)
        return ResolvedTicketImportResponse(
            tickets=[ResolvedTicketResponse.model_validate(r) for r in inserted],
            source_status="sample_import",
            source_warning=(
                "Loaded from built-in sample data. "
                "These records are labeled source='sample' and are not from live Jira."
            ),
            skipped_duplicates=skipped,
        )

    # source == "jira"
    result = _fetch_from_jira()
    source_status: str = result["source_status"]
    source_warning: str | None = result["source_warning"]

    if source_status != "jira":
        # credentials_missing or jira_error — return immediately, no insertion
        return ResolvedTicketImportResponse(
            tickets=[],
            source_status=source_status,
            source_warning=source_warning,
            skipped_duplicates=0,
        )

    inserted, skipped = _upsert_tickets(result["tickets"], db)
    return ResolvedTicketImportResponse(
        tickets=[ResolvedTicketResponse.model_validate(r) for r in inserted],
        source_status="jira",
        source_warning=source_warning,
        skipped_duplicates=skipped,
    )


# ---------------------------------------------------------------------------
# GET /api/resolved-tickets
# ---------------------------------------------------------------------------

@router.get("", response_model=ResolvedTicketListResponse)
def list_resolved_tickets(
    db: Session = Depends(get_db),
) -> ResolvedTicketListResponse:
    """Return all resolved tickets with total count."""
    tickets = db.query(ResolvedTicket).order_by(ResolvedTicket.created_at.desc()).all()
    return ResolvedTicketListResponse(
        tickets=[ResolvedTicketResponse.model_validate(t) for t in tickets],
        total=len(tickets),
    )
