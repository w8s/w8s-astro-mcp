"""Integration tests for MCP server tools with SQLite database.

These tests verify the full workflow:
1. Database → Server tools → Response
2. Real tool calls like setup_astro_config, get_natal_chart, get_transits

Skipped in CI (where no production DB exists) via the CI env var.
Run locally with no special setup — all tests use a temporary database.
"""

import os
import pytest
from pathlib import Path
import tempfile
from datetime import datetime

from w8s_astro_mcp.database import initialize_database, get_session
from w8s_astro_mcp.models import Profile, Location, HouseSystem
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper


# Skip the entire module in CI environments.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Integration tests require a local temp DB; skipped in CI"
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with seeded reference data."""
    db_path = tmp_path / "test_astro.db"
    engine = initialize_database(db_path, echo=False)

    with get_session(engine) as session:
        for code, name in [("P", "Placidus"), ("K", "Koch"), ("E", "Equal")]:
            session.add(HouseSystem(code=code, name=name, description=f"{name} house system"))
        session.commit()

    yield db_path, engine


@pytest.fixture
def db_helper(temp_db):
    """DatabaseHelper wired to the temporary database."""
    db_path, _engine = temp_db
    return DatabaseHelper(db_path=str(db_path))


def test_setup_astro_config_workflow(db_helper, temp_db):
    """Simulate the setup_astro_config MCP tool: create profile + birth location."""
    _db_path, engine = temp_db

    profile = db_helper.create_profile_with_location(
        name="Test User",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago"
    )

    with get_session(engine) as session:
        retrieved = session.query(Profile).filter_by(id=profile.id).first()
        assert retrieved is not None
        assert retrieved.birth_date == "1981-05-06"
        assert retrieved.birth_time == "00:50"

        birth_loc = session.query(Location).filter_by(id=retrieved.birth_location_id).first()
        assert birth_loc is not None
        assert birth_loc.latitude == 32.9483


def test_database_helper_get_primary_profile(db_helper, temp_db):
    """DatabaseHelper.get_current_profile() returns the profile after it is set as current."""
    _db_path, engine = temp_db

    profile = db_helper.create_profile_with_location(
        name="Primary User",
        birth_date="1990-01-15",
        birth_time="12:00",
        birth_location_name="Test City",
        birth_latitude=40.0,
        birth_longitude=-95.0,
        birth_timezone="America/Chicago"
    )

    db_helper.set_current_profile(profile.id)

    current = db_helper.get_current_profile()
    assert current is not None
    assert current.name == "Primary User"


def test_get_natal_chart_with_cached_data(db_helper, temp_db):
    """Simulate get_natal_chart: store natal data then retrieve it."""
    _db_path, engine = temp_db

    from w8s_astro_mcp.models import NatalPlanet, NatalHouse, NatalPoint

    profile = db_helper.create_profile_with_location(
        name="Test User",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago"
    )

    with get_session(engine) as session:
        house_system = session.query(HouseSystem).filter_by(code='P').first()

        session.add(NatalPlanet(
            profile_id=profile.id, planet="Sun",
            degree=15, minutes=24, seconds=36.0,
            sign="Taurus", absolute_position=45.41, house_number=7
        ))
        session.add(NatalPoint(
            profile_id=profile.id, house_system_id=house_system.id,
            point_type="ASC", degree=11, minutes=45, seconds=0.0,
            sign="Scorpio", absolute_position=221.75
        ))
        session.add(NatalHouse(
            profile_id=profile.id, house_system_id=house_system.id,
            house_number=1, degree=11, minutes=45, seconds=0.0,
            sign="Scorpio", absolute_position=221.75
        ))
        session.commit()

        planets = session.query(NatalPlanet).filter_by(profile_id=profile.id).all()
        assert len(planets) == 1
        assert planets[0].planet == "Sun"
        assert planets[0].sign == "Taurus"

        points = session.query(NatalPoint).filter_by(profile_id=profile.id).all()
        assert len(points) == 1
        assert points[0].point_type == "ASC"

        houses = session.query(NatalHouse).filter_by(profile_id=profile.id).all()
        assert len(houses) == 1
        assert houses[0].house_number == 1


def test_location_management(db_helper, temp_db):
    """Create a profile then add and query multiple locations."""
    _db_path, engine = temp_db

    profile = db_helper.create_profile_with_location(
        name="Test User",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="St. Louis, MO",
        birth_latitude=38.627,
        birth_longitude=-90.198,
        birth_timezone="America/Chicago"
    )

    db_helper.create_location(
        profile_id=profile.id,
        label="Richardson, TX",
        latitude=32.9483,
        longitude=-96.7299,
        timezone="America/Chicago",
        set_as_home=True
    )
    db_helper.create_location(
        profile_id=profile.id,
        label="New York, NY",
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York",
        set_as_home=False
    )

    with get_session(engine) as session:
        all_locations = session.query(Location).filter_by(profile_id=profile.id).all()
        assert len(all_locations) == 3  # birth + Richardson + NYC

        home = session.query(Location).filter_by(
            profile_id=profile.id, is_current_home=True
        ).first()
        assert home is not None
        assert home.label == "Richardson, TX"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
