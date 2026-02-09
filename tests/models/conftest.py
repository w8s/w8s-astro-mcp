"""Pytest fixtures for model tests.

Provides reusable fixtures for database testing:
- test_engine: Clean SQLite database for each test
- test_session: Database session with automatic rollback
- seeded_house_systems: Pre-populated house systems
"""

import pytest
from pathlib import Path
import tempfile
import os

from w8s_astro_mcp.database import create_db_engine, create_tables, get_session_factory
from w8s_astro_mcp.models import HouseSystem, HOUSE_SYSTEM_SEED_DATA


@pytest.fixture(scope="function")
def test_engine():
    """
    Create a fresh test database for each test function.
    
    Uses a temporary SQLite database that's deleted after the test.
    """
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Create engine and tables
    engine = create_db_engine(Path(db_path), echo=False)
    
    # Import all models to register them with Base.metadata
    from w8s_astro_mcp.models import HouseSystem  # noqa: F401
    
    create_tables(engine)
    
    yield engine
    
    # Cleanup
    engine.dispose()
    if Path(db_path).exists():
        os.unlink(db_path)


@pytest.fixture(scope="function")
def test_session(test_engine):
    """
    Create a database session for testing.
    
    Automatically rolls back after each test to keep tests isolated.
    """
    SessionFactory = get_session_factory(test_engine)
    session = SessionFactory()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def seeded_house_systems(test_session):
    """
    Pre-populate database with house systems.
    
    Returns the list of created HouseSystem instances.
    """
    house_systems = []
    for data in HOUSE_SYSTEM_SEED_DATA:
        hs = HouseSystem(**data)
        test_session.add(hs)
        house_systems.append(hs)
    
    test_session.commit()
    
    return house_systems
