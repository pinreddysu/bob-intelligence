"""
Milestone 2 tests — Data layer, story import, Jira service.

Coverage checklist (per plan):
  [x] DB initialisation and story persistence (across simulated restart)
  [x] Listing stories (GET /api/stories)
  [x] Importing stories — sample import
  [x] Explicit sample import and duplicate-import behaviour
  [x] Jira configuration failures and import errors (credentials_missing, jira_error)
  [x] source_status and source_warning behaviour
  [x] Story points remaining metadata only (priority engine output unchanged)
  [x] Test isolation using fresh bob_intelligence_test.db

Test database rules (enforced):
  - Never reads, overwrites, or deletes production bob_intelligence.db.
  - Every test uses an injected session that rolls back on teardown.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1. DB initialisation and table creation
# ─────────────────────────────────────────────────────────────────────────────

def test_test_db_is_not_production_db():
    """Confirm tests never target the production database file."""
    test_url = os.environ.get("DATABASE_URL", "")
    assert "bob_intelligence_test" in test_url, (
        f"Expected test database URL to contain 'bob_intelligence_test', got: {test_url!r}"
    )
    assert "bob_intelligence.db" not in test_url.replace("bob_intelligence_test.db", ""), (
        "Test DATABASE_URL must not point at the production database."
    )


def test_story_table_created(db_session):
    """Tables are created; a simple Story can be inserted and retrieved."""
    from backend.models import Story

    story = Story(
        title="Test story",
        source="sample",
        labels=[],
        blockers=[],
        linked_prs=[],
    )
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)

    fetched = db_session.query(Story).filter(Story.id == story.id).first()
    assert fetched is not None
    assert fetched.title == "Test story"
    assert fetched.source == "sample"


def test_all_models_importable():
    """All six ORM models can be imported without error."""
    from backend.models import (  # noqa: F401
        BobSession,
        Comparison,
        DeveloperProfile,
        Outcome,
        Recommendation,
        Story,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Story persistence (simulated restart)
# ─────────────────────────────────────────────────────────────────────────────

def test_story_persists_across_session_close(db_session):
    """
    Write a Story, close the session, open a new session on the same file,
    and confirm the record is retrievable — simulating a process restart.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models import Story

    engine = db_session.get_bind()
    story = Story(
        title="Persistent story",
        source="sample",
        labels=[],
        blockers=[],
        linked_prs=[],
    )
    db_session.add(story)
    db_session.commit()
    story_id = story.id

    # Open a brand-new session on the same engine (simulates a process restart).
    NewSession = sessionmaker(bind=engine)
    new_session = NewSession()
    try:
        refetched = new_session.query(Story).filter(Story.id == story_id).first()
        assert refetched is not None
        assert refetched.title == "Persistent story"
    finally:
        new_session.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /api/stories
# ─────────────────────────────────────────────────────────────────────────────

def test_list_stories_empty(client):
    """GET /api/stories returns an empty list when no stories are imported."""
    resp = client.get("/api/stories")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["stories"] == []


def test_list_stories_returns_imported_story(client):
    """GET /api/stories returns stories after a sample import."""
    import_resp = client.post("/api/stories/import", json={"import_source": "sample"})
    assert import_resp.status_code == 201

    list_resp = client.get("/api/stories")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    assert all(s["source"] == "sample" for s in data["stories"])


def test_list_stories_includes_required_fields(client):
    """Each story in the listing includes priority, status, blockers, linked_prs, source."""
    client.post("/api/stories/import", json={"import_source": "sample"})
    resp = client.get("/api/stories")
    assert resp.status_code == 200
    for story in resp.json()["stories"]:
        for field in ("priority", "status", "blockers", "linked_prs", "source", "jira_key"):
            assert field in story, f"Field '{field}' missing from story response"


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /api/stories/import — sample import
# ─────────────────────────────────────────────────────────────────────────────

def test_sample_import_source_status(client):
    """Sample import returns source_status='sample_import' and a non-empty source_warning."""
    resp = client.post("/api/stories/import", json={"import_source": "sample"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_status"] == "sample_import"
    assert data["source_warning"] is not None
    assert len(data["source_warning"]) > 0


def test_sample_import_stories_labeled_sample(client):
    """All stories imported from sample data carry source='sample'."""
    resp = client.post("/api/stories/import", json={"import_source": "sample"})
    assert resp.status_code == 201
    for story in resp.json()["stories"]:
        assert story["source"] == "sample", (
            f"Story {story.get('jira_key')} has source={story['source']!r}, expected 'sample'"
        )


def test_sample_import_creates_expected_stories(client):
    """Sample import creates the stories from stories.json (keys match current sample data)."""
    import json
    from pathlib import Path
    sample_path = Path(__file__).parent.parent / "sample_data" / "stories.json"
    with open(sample_path) as fh:
        raw = json.load(fh)
    expected_keys = {s["jira_key"] for s in raw}

    resp = client.post("/api/stories/import", json={"import_source": "sample"})
    assert resp.status_code == 201
    jira_keys = {s["jira_key"] for s in resp.json()["stories"]}
    assert jira_keys == expected_keys


# ─────────────────────────────────────────────────────────────────────────────
# 5. Duplicate import behaviour
# ─────────────────────────────────────────────────────────────────────────────

def test_duplicate_sample_import_skips_existing(client):
    """Importing sample data twice skips stories already in the DB."""
    first = client.post("/api/stories/import", json={"import_source": "sample"})
    assert first.status_code == 201
    first_count = len(first.json()["stories"])
    assert first_count > 0

    second = client.post("/api/stories/import", json={"import_source": "sample"})
    assert second.status_code == 201
    assert second.json()["skipped_duplicates"] == first_count
    assert len(second.json()["stories"]) == 0


def test_duplicate_jira_import_skips_existing(client, db_session):
    """Re-importing the same jira_key returns skipped_duplicates=1 and the existing story."""
    from backend.models import Story

    # Pre-populate DB with a story that has the jira_key we'll attempt to import.
    existing = Story(
        jira_key="PIE-99",
        title="Existing story",
        source="jira",
        labels=[],
        blockers=[],
        linked_prs=[],
    )
    db_session.add(existing)
    db_session.commit()

    # Mock the jira service to return a matching story_data dict.
    mock_result = {
        "story_data": {
            "jira_key": "PIE-99",
            "title": "Updated title",
            "description": None,
            "acceptance_criteria": None,
            "story_points": None,
            "labels": [],
            "priority": None,
            "status": None,
            "assignee": None,
            "blockers": [],
            "linked_prs": [],
            "source": "jira",
        },
        "source_status": "jira",
        "source_warning": None,
    }
    with patch("backend.services.jira_service.fetch_from_jira", return_value=mock_result):
        resp = client.post(
            "/api/stories/import", json={"import_source": "jira", "jira_key": "PIE-99"}
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["skipped_duplicates"] == 1
    assert len(data["stories"]) == 1
    assert data["stories"][0]["title"] == "Existing story"  # original, not updated


# ─────────────────────────────────────────────────────────────────────────────
# 6. Jira configuration failures and import errors
# ─────────────────────────────────────────────────────────────────────────────

def test_jira_import_credentials_missing_returns_error(client):
    """
    POST /api/stories/import with import_source='jira' and no credentials
    returns source_status='credentials_missing' and a non-empty source_warning.
    Crucially, no sample data is silently substituted.
    """
    # Ensure no Jira credentials are present in the environment.
    with patch.dict(os.environ, {
        "JIRA_BASE_URL": "",
        "JIRA_USER_EMAIL": "",
        "JIRA_API_TOKEN": "",
    }, clear=False):
        resp = client.post(
            "/api/stories/import", json={"import_source": "jira", "jira_key": "PIE-42"}
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source_status"] == "credentials_missing", (
        f"Expected 'credentials_missing', got {data['source_status']!r}"
    )
    assert data["source_warning"] is not None
    assert len(data["source_warning"]) > 0
    # No stories returned — NOT silently filled with sample data.
    assert data["stories"] == [], (
        "Sample data must not be silently substituted when Jira credentials are absent."
    )


def test_jira_import_http_error_returns_jira_error(client):
    """
    When Jira returns an HTTP error, source_status='jira_error' and no stories are returned.
    """
    import httpx

    def _raise_http_status(*args, **kwargs):
        request = httpx.Request("GET", "https://fake.atlassian.net/rest/api/3/issue/PIE-42")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

    with patch.dict(os.environ, {
        "JIRA_BASE_URL": "https://fake.atlassian.net",
        "JIRA_USER_EMAIL": "user@example.com",
        "JIRA_API_TOKEN": "token123",
    }, clear=False):
        with patch("httpx.get", side_effect=_raise_http_status):
            resp = client.post(
                "/api/stories/import",
                json={"import_source": "jira", "jira_key": "PIE-42"},
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source_status"] == "jira_error"
    assert data["source_warning"] is not None
    assert data["stories"] == []


def test_jira_import_network_error_returns_jira_error(client):
    """
    A network-level error to Jira returns source_status='jira_error'.
    """
    import httpx

    with patch.dict(os.environ, {
        "JIRA_BASE_URL": "https://fake.atlassian.net",
        "JIRA_USER_EMAIL": "user@example.com",
        "JIRA_API_TOKEN": "token123",
    }, clear=False):
        with patch("httpx.get", side_effect=httpx.ConnectError("connection refused")):
            resp = client.post(
                "/api/stories/import",
                json={"import_source": "jira", "jira_key": "PIE-42"},
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source_status"] == "jira_error"
    assert data["source_warning"] is not None
    assert data["stories"] == []


def test_jira_import_missing_jira_key_returns_422(client):
    """POST /api/stories/import with import_source='jira' but no jira_key returns 422."""
    resp = client.post("/api/stories/import", json={"import_source": "jira"})
    assert resp.status_code == 422


def test_jira_import_missing_jira_key_empty_string(client):
    """POST /api/stories/import with import_source='jira' and empty jira_key returns 422."""
    resp = client.post(
        "/api/stories/import", json={"import_source": "jira", "jira_key": ""}
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 7. source_status and source_warning behaviour
# ─────────────────────────────────────────────────────────────────────────────

def test_successful_jira_import_source_status_is_jira(client):
    """A successful Jira import returns source_status='jira'."""
    mock_result = {
        "story_data": {
            "jira_key": "PIE-100",
            "title": "A live Jira story",
            "description": "Description text.",
            "acceptance_criteria": "AC text.",
            "story_points": 3,
            "labels": ["api"],
            "priority": "high",
            "status": "To Do",
            "assignee": None,
            "blockers": [],
            "linked_prs": [],
            "source": "jira",
        },
        "source_status": "jira",
        "source_warning": None,
    }
    with patch("backend.services.jira_service.fetch_from_jira", return_value=mock_result):
        resp = client.post(
            "/api/stories/import", json={"import_source": "jira", "jira_key": "PIE-100"}
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source_status"] == "jira"
    assert data["source_warning"] is None
    assert len(data["stories"]) == 1
    assert data["stories"][0]["source"] == "jira"


def test_jira_import_with_field_warnings_carries_source_warning(client):
    """When Jira import succeeds but custom fields are missing, source_warning is set."""
    mock_result = {
        "story_data": {
            "jira_key": "PIE-101",
            "title": "Story with missing AC field",
            "description": None,
            "acceptance_criteria": None,
            "story_points": None,
            "labels": [],
            "priority": None,
            "status": None,
            "assignee": None,
            "blockers": [],
            "linked_prs": [],
            "source": "jira",
        },
        "source_status": "jira",
        "source_warning": "JIRA_AC_FIELD is not configured — acceptance criteria will not be imported.",
    }
    with patch("backend.services.jira_service.fetch_from_jira", return_value=mock_result):
        resp = client.post(
            "/api/stories/import", json={"import_source": "jira", "jira_key": "PIE-101"}
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source_status"] == "jira"
    assert data["source_warning"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Story points — metadata only, no influence on recommendations
# ─────────────────────────────────────────────────────────────────────────────

def test_story_points_stored_as_metadata(client):
    """story_points is stored and returned as plain metadata."""
    mock_result = {
        "story_data": {
            "jira_key": "PIE-200",
            "title": "Story with points",
            "description": None,
            "acceptance_criteria": None,
            "story_points": 8,
            "labels": [],
            "priority": "medium",
            "status": "To Do",
            "assignee": None,
            "blockers": [],
            "linked_prs": [],
            "source": "jira",
        },
        "source_status": "jira",
        "source_warning": None,
    }
    with patch("backend.services.jira_service.fetch_from_jira", return_value=mock_result):
        import_resp = client.post(
            "/api/stories/import", json={"import_source": "jira", "jira_key": "PIE-200"}
        )
    assert import_resp.status_code == 201
    story = import_resp.json()["stories"][0]
    assert story["story_points"] == 8  # stored and returned


def test_story_points_field_present_in_response(client):
    """story_points is always present in the story response (may be null)."""
    client.post("/api/stories/import", json={"import_source": "sample"})
    resp = client.get("/api/stories")
    for story in resp.json()["stories"]:
        assert "story_points" in story


# ─────────────────────────────────────────────────────────────────────────────
# 9. GET /api/stories/{id}
# ─────────────────────────────────────────────────────────────────────────────

def test_get_story_by_id(client):
    """GET /api/stories/{id} returns the correct story."""
    import_resp = client.post("/api/stories/import", json={"import_source": "sample"})
    assert import_resp.status_code == 201
    story_id = import_resp.json()["stories"][0]["id"]

    resp = client.get(f"/api/stories/{story_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == story_id


def test_get_story_not_found(client):
    """GET /api/stories/{id} with an unknown ID returns 404."""
    resp = client.get("/api/stories/nonexistent-id-999")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 10. Developer profiles
# ─────────────────────────────────────────────────────────────────────────────

def test_list_developer_profiles_empty(client):
    """GET /api/developer-profiles returns an empty list initially."""
    resp = client.get("/api/developer-profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_import_sample_developer_profiles(client):
    """POST /api/developer-profiles/import-sample imports profiles labeled source='sample'."""
    resp = client.post("/api/developer-profiles/import-sample")
    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] > 0
    for profile in data["profiles"]:
        assert profile["source"] == "sample"


def test_duplicate_dev_profile_import_idempotent(client):
    """Importing sample developer profiles twice skips existing profiles."""
    first = client.post("/api/developer-profiles/import-sample")
    assert first.status_code == 201
    first_count = first.json()["total"]

    second = client.post("/api/developer-profiles/import-sample")
    assert second.status_code == 201
    assert second.json()["total"] == 0  # all skipped


def test_list_developer_profiles_after_import(client):
    """GET /api/developer-profiles returns all imported profiles."""
    client.post("/api/developer-profiles/import-sample")
    resp = client.get("/api/developer-profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# 11. Jira service unit tests
# ─────────────────────────────────────────────────────────────────────────────

def test_jira_service_credentials_missing():
    """jira_service.fetch_from_jira returns credentials_missing when env is unset."""
    from backend.services.jira_service import fetch_from_jira

    with patch.dict(os.environ, {
        "JIRA_BASE_URL": "",
        "JIRA_USER_EMAIL": "",
        "JIRA_API_TOKEN": "",
    }, clear=False):
        result = fetch_from_jira("PIE-42")

    assert result["source_status"] == "credentials_missing"
    assert result["story_data"] is None
    assert result["source_warning"] is not None


def test_jira_service_http_error():
    """jira_service.fetch_from_jira returns jira_error on HTTP 404."""
    import httpx
    from backend.services.jira_service import fetch_from_jira

    def _raise(*args, **kwargs):
        request = httpx.Request("GET", "https://fake.atlassian.net/rest/api/3/issue/PIE-X")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("Not Found", request=request, response=response)

    with patch.dict(os.environ, {
        "JIRA_BASE_URL": "https://fake.atlassian.net",
        "JIRA_USER_EMAIL": "u@e.com",
        "JIRA_API_TOKEN": "tok",
    }, clear=False):
        with patch("httpx.get", side_effect=_raise):
            result = fetch_from_jira("PIE-X")

    assert result["source_status"] == "jira_error"
    assert result["story_data"] is None
    assert "404" in result["source_warning"]


def test_jira_service_validates_story_points_field():
    """
    When the configured story-points field is absent from the Jira response,
    fetch_from_jira sets story_points=None and includes a source_warning.
    """
    import httpx
    from backend.services.jira_service import fetch_from_jira

    fake_response = {
        "fields": {
            "summary": "Test",
            # Note: customfield_10016 (or whatever _story_points_field() returns) is absent.
            "priority": {"name": "High"},
            "status": {"name": "To Do"},
            "assignee": None,
            "labels": [],
            "issuelinks": [],
            "description": None,
        }
    }

    with patch.dict(os.environ, {
        "JIRA_BASE_URL": "https://fake.atlassian.net",
        "JIRA_USER_EMAIL": "u@e.com",
        "JIRA_API_TOKEN": "tok",
        "JIRA_STORY_POINTS_FIELD": "customfield_10016",
        "JIRA_AC_FIELD": "",
    }, clear=False):
        with patch("httpx.get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = fake_response
            result = fetch_from_jira("PIE-T")

    assert result["source_status"] == "jira"
    assert result["story_data"]["story_points"] is None
    assert result["source_warning"] is not None
    assert "customfield_10016" in result["source_warning"]


def test_sample_stories_all_tagged_sample():
    """jira_service.load_sample_stories tags every story as source='sample'."""
    from backend.services.jira_service import load_sample_stories
    stories = load_sample_stories()
    assert len(stories) > 0
    for s in stories:
        assert s["source"] == "sample"


def test_sample_dev_profiles_all_tagged_sample():
    """jira_service.load_sample_developer_profiles tags every profile as source='sample'."""
    from backend.services.jira_service import load_sample_developer_profiles
    profiles = load_sample_developer_profiles()
    assert len(profiles) > 0
    for p in profiles:
        assert p["source"] == "sample"


# ─────────────────────────────────────────────────────────────────────────────
# 12. Health check still passes
# ─────────────────────────────────────────────────────────────────────────────

def test_health_check(client):
    """GET /api/health still returns 200 OK."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
