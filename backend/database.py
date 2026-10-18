"""
Database engine and session factory.

Production:  file-backed SQLite at ./bob_intelligence.db
Tests:       isolated file at ./bob_intelligence_test.db
             (configured by setting DATABASE_URL in conftest.py before importing
              this module, or by overriding app dependencies)

Milestone 2: updated from in-memory stub to file-backed SQLite.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# Default to file-backed SQLite for production; tests override this via the
# TEST_DATABASE_URL environment variable set in conftest.py.
_DEFAULT_DATABASE_URL = "sqlite:///./bob_intelligence.db"
DATABASE_URL: str = os.getenv("DATABASE_URL") or _DEFAULT_DATABASE_URL

# check_same_thread=False is required for SQLite with FastAPI's threaded handling.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Enable WAL mode and foreign key constraints on every SQLite connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if not DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables.  Safe to call on every startup (no-op if tables exist)."""
    # Import models so their table metadata is registered on Base before create_all.
    import backend.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
