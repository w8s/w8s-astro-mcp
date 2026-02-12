"""Database connection and session management for w8s-astro-mcp.

This module provides SQLAlchemy database setup for storing:
- Multiple astrological profiles (birth data + cached natal charts)
- Transit lookup history
- Future: aspects, progressions, etc.

Database location: ~/.w8s-astro-mcp/astro.db
"""

from pathlib import Path
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# SQLAlchemy Base class for all models
Base = declarative_base()


class DatabaseError(Exception):
    """Raised when database operations fail."""
    pass


def get_database_path() -> Path:
    """
    Get the path to the SQLite database file.
    
    Returns:
        Path to ~/.w8s-astro-mcp/astro.db
    """
    db_dir = Path.home() / ".w8s-astro-mcp"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "astro.db"


def create_db_engine(db_path: Path | None = None, echo: bool = False) -> Engine:
    """
    Create SQLAlchemy engine for SQLite database.
    
    Args:
        db_path: Optional custom database path (defaults to ~/.w8s-astro-mcp/astro.db)
        echo: If True, log all SQL statements (useful for debugging)
    
    Returns:
        SQLAlchemy Engine instance
    """
    if db_path is None:
        db_path = get_database_path()
    
    # SQLite connection string
    connection_string = f"sqlite:///{db_path}"
    
    # Create engine with SQLite-specific settings
    engine = create_engine(
        connection_string,
        echo=echo,
        # SQLite-specific optimizations
        connect_args={
            "check_same_thread": False,  # Allow multi-threaded access
        },
    )
    
    # Enable foreign key constraints (disabled by default in SQLite)
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    return engine


def create_tables(engine: Engine) -> None:
    """
    Create all database tables.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    Base.metadata.create_all(engine)


def get_session_factory(engine: Engine) -> sessionmaker:
    """
    Create a session factory for the given engine.
    
    Args:
        engine: SQLAlchemy engine instance
    
    Returns:
        Sessionmaker instance for creating sessions
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Usage:
        with get_session() as session:
            profile = session.query(Profile).first()
    
    Args:
        engine: Optional engine (creates default if not provided)
    
    Yields:
        SQLAlchemy Session
    
    Raises:
        DatabaseError: If session operations fail
    """
    if engine is None:
        engine = create_db_engine()
    
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()
    
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise DatabaseError(f"Database operation failed: {e}") from e
    finally:
        session.close()


def initialize_database(db_path: Path | None = None, echo: bool = False) -> Engine:
    """
    Initialize the database with all tables.
    
    This is a convenience function that:
    1. Creates the database engine
    2. Creates all tables if they don't exist
    3. Returns the engine for further use
    
    Args:
        db_path: Optional custom database path
        echo: If True, log all SQL statements
    
    Returns:
        SQLAlchemy Engine instance
    
    Example:
        engine = initialize_database()
        with get_session(engine) as session:
            profiles = session.query(Profile).all()
    """
    engine = create_db_engine(db_path, echo)
    create_tables(engine)
    return engine


# Module-level engine for easy access
# This will be initialized when needed
_engine: Engine | None = None


def get_engine(db_path: Path | None = None, echo: bool = False) -> Engine:
    """
    Get or create the module-level database engine.
    
    This creates a single engine instance that's reused across the application.
    
    Args:
        db_path: Optional custom database path
        echo: If True, log all SQL statements
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is None:
        _engine = initialize_database(db_path, echo)
    return _engine
