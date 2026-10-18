"""
conftest.py — pytest fixtures for Milestone 2.

Test isolation rules (from the plan):
  - Tests use a separate file-backed SQLite at bob_intelligence_test.db.
  - The test DB is created fresh at session start and deleted on teardown.
  - Each test gets a clean slate: all tables are truncated between tests.
  - Production bob_intelligence.db is NEVER touched by tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set the test DATABASE_URL before importing anything that touches database.py.
# Use an in-memory SQLite database keyed to a shared file so the test DB is
# isolated per test via a SQLite shared-cache URI.
_TEST_DB_PATH = Path(__file__).parent / "bob_intelligence_test.db"
_TEST_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"

# Override env vars BEFORE importing app modules that read them at import time.
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
# Prevent main.py lifespan from auto-seeding sample resolved tickets into the test DB.
os.environ["BOB_SKIP_SAMPLE_SEED"] = "1"


def _make_test_engine():
    return create_engine(
        _TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )


# ---------------------------------------------------------------------------
# LLM stub — session-scoped, autouse: patches both LLM calls for the entire
# test session so no network request is ever made during tests.
# analyze_ticket_readiness returns (None, None) — callers handle None gracefully.
# analyze_mode returns a ModeAnalysis with llm_used=False so the deterministic
# rule engine mode is used (per the fix in recommendation_service.generate).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def mock_llm_calls():
    from backend.services.llm_service import ModeAnalysis  # noqa: PLC0415

    _readiness_stub = MagicMock(return_value=(None, None))
    _mode_stub = MagicMock(return_value=ModeAnalysis(
        mode="collaborative",
        rationale="LLM stubbed out in tests.",
        warning=None,
        llm_used=False,
    ))

    with (
        patch("backend.services.llm_service.analyze_ticket_readiness", _readiness_stub),
        patch("backend.services.llm_service.analyze_mode", _mode_stub),
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def test_db_lifecycle():
    """
    Session-scoped: create the test DB on entry; delete the file on teardown.
    Guarantees the production DB is never used.
    """
    # Safety assertion: confirm test URL is distinct from production.
    assert "bob_intelligence_test" in _TEST_DATABASE_URL

    from backend.database import Base  # noqa: PLC0415
    import backend.models  # noqa: F401, PLC0415

    engine = _make_test_engine()
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    yield

    # Teardown — delete the test DB file so it never bleeds into production.
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def clean_tables():
    """
    Function-scoped: truncate all tables before each test so every test
    starts with an empty database.  This is cheaper than recreating the
    schema for each test.
    """
    from backend.database import Base  # noqa: PLC0415
    import backend.models  # noqa: F401, PLC0415

    engine = _make_test_engine()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    engine.dispose()


@pytest.fixture()
def db_session():
    """
    Yield a SQLAlchemy session backed by the test DB.
    The session is closed (not rolled back) after each test;
    test isolation is guaranteed by the clean_tables fixture above.
    """
    from backend.database import Base  # noqa: PLC0415
    import backend.models  # noqa: F401, PLC0415

    engine = _make_test_engine()
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """
    FastAPI TestClient wired to the test DB via dependency override.
    Uses the same session as db_session so tests can pre-populate data.
    """
    from backend.main import app  # noqa: PLC0415
    from backend.database import get_db  # noqa: PLC0415

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
