"""
Database configuration for CAATmaster - SQLite version
Adapted from PostgreSQL to SQLite for portability
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager

# The database (holds hashed user passwords - core.models.User) lives
# under the user's home directory, the same convention already used for
# everything else the app persists locally (recent_projects.py,
# session_state.py, ai_service.py's credential store all use
# Path.home()/".caatmaster" or ".config/caatmaster") - NOT inside the
# project/installation directory. Two concrete problems the old
# `Path(__file__).parent.parent.parent / "data"` location caused:
#   1. It sat inside the git working tree with no .gitignore entry, so
#      the real database - hashed passwords included - was repeatedly
#      committed to source control across many commits.
#   2. For a packaged/portable build, a path derived from the running
#      module's location is not a reliably writable, persistent location -
#      a PyInstaller --onefile build in particular extracts to a fresh
#      temp directory every launch, so a database written there would
#      silently lose all data (including registered users) every time the
#      app closed.
DATA_DIR = Path.home() / ".caatmaster" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database file path
DB_PATH = DATA_DIR / "caatmaster.db"

# One-time migration for anyone with a pre-existing database at the old,
# project-relative location: copy it forward rather than silently
# starting empty (which would look like every registered user vanished).
# Only runs when the new location doesn't have a database yet, so it
# never overwrites real data once the move has happened.
_LEGACY_DB_PATH = Path(__file__).parent.parent.parent / "data" / "caatmaster.db"
if not DB_PATH.exists() and _LEGACY_DB_PATH.exists():
    import shutil as _shutil
    _shutil.copy2(_LEGACY_DB_PATH, DB_PATH)

# SQLite database URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create SQLAlchemy engine
# SQLite specific configurations for better performance and concurrency
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Allow multi-threading
    poolclass=StaticPool,  # Simple pool for SQLite
    echo=False,  # Set to True for SQL query debugging
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Create Base class for models
Base = declarative_base()


def init_db():
    """Initialize the database, creating all tables"""
    from . import models  # Import models to ensure they're registered
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DB_PATH}")


def get_db():
    """
    Dependency for getting database sessions
    Usage in desktop app - not for web frameworks
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions
    Usage:
        with get_db_context() as db:
            # do database operations
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_path():
    """Return the database file path"""
    return str(DB_PATH)


def backup_db(backup_path: str = None):
    """
    Create a backup of the database
    Args:
        backup_path: Path for backup file. If None, creates timestamped backup
    """
    import shutil
    from datetime import datetime

    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DATA_DIR / f"caatmaster_backup_{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)
    return str(backup_path)


def reset_db():
    """
    WARNING: This will delete all data!
    Drops all tables and recreates them
    """
    from . import models
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print(f"Database reset at: {DB_PATH}")
