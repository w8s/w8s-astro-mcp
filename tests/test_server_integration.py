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


def test_save_natal_chart_and_retrieve(db_helper, temp_db):
    """save_natal_chart() persists data; get_natal_chart_data() returns it correctly."""
    _db_path, engine = temp_db

    profile = db_helper.create_profile_with_location(
        name="Natal Save Test",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago",
    )

    # Minimal chart_data that mirrors EphemerisEngine output
    fake_chart = {
        "planets": {
            "Sun": {"sign": "Taurus", "degree": 15.41, "is_retrograde": False},
            "Moon": {"sign": "Gemini", "degree": 11.86, "is_retrograde": False},
        },
        "houses": {
            "1": {"sign": "Scorpio", "degree": 11.75},
            "7": {"sign": "Taurus", "degree": 11.75},
        },
        "points": {
            "ASC": {"sign": "Scorpio", "degree": 11.75},
            "MC":  {"sign": "Leo", "degree": 5.0},
        },
    }

    db_helper.save_natal_chart(profile, fake_chart, house_system_id=1)

    result = db_helper.get_natal_chart_data(profile)

    assert "Sun" in result["planets"]
    assert result["planets"]["Sun"]["sign"] == "Taurus"
    assert "Moon" in result["planets"]
    assert "1" in result["houses"]
    assert "ASC" in result["points"]
    assert result["points"]["ASC"]["sign"] == "Scorpio"


def test_save_natal_chart_idempotent(db_helper, temp_db):
    """Calling save_natal_chart() twice replaces old data rather than duplicating it."""
    _db_path, engine = temp_db
    from w8s_astro_mcp.models import NatalPlanet

    profile = db_helper.create_profile_with_location(
        name="Idempotent Test",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago",
    )

    chart_v1 = {
        "planets": {"Sun": {"sign": "Taurus", "degree": 15.0, "is_retrograde": False}},
        "houses": {"1": {"sign": "Scorpio", "degree": 11.0}},
        "points": {"ASC": {"sign": "Scorpio", "degree": 11.0}},
    }
    chart_v2 = {
        "planets": {
            "Sun": {"sign": "Taurus", "degree": 15.41, "is_retrograde": False},
            "Moon": {"sign": "Gemini", "degree": 11.86, "is_retrograde": False},
        },
        "houses": {"1": {"sign": "Scorpio", "degree": 11.75}},
        "points": {"ASC": {"sign": "Scorpio", "degree": 11.75}},
    }

    db_helper.save_natal_chart(profile, chart_v1, house_system_id=1)
    db_helper.save_natal_chart(profile, chart_v2, house_system_id=1)

    with get_session(engine) as session:
        planets = session.query(NatalPlanet).filter_by(profile_id=profile.id).all()
        # Should have exactly 2 (Sun + Moon from v2), not 3 (Sun×2 + Moon)
        assert len(planets) == 2
        names = {p.planet for p in planets}
        assert names == {"Sun", "Moon"}


def _make_profile_with_transits(db_helper, engine):
    """Helper: create a profile and seed two transit lookups."""
    from datetime import datetime
    from w8s_astro_mcp.models import TransitLookup, TransitPlanet, Location
    from w8s_astro_mcp.database import get_session

    profile = db_helper.create_profile_with_location(
        name="History Test",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago",
    )

    with get_session(engine) as session:
        loc = session.query(Location).filter_by(profile_id=profile.id).first()

        for dt_str, mercury_sign in [
            ("2026-01-01T12:00:00", "Capricorn"),
            ("2026-02-01T12:00:00", "Aquarius"),
        ]:
            lookup = TransitLookup(
                profile_id=profile.id,
                location_id=loc.id,
                house_system_id=1,
                lookup_datetime=datetime.fromisoformat(dt_str),
                location_snapshot_label=loc.label,
                location_snapshot_latitude=loc.latitude,
                location_snapshot_longitude=loc.longitude,
                location_snapshot_timezone=loc.timezone,
            )
            session.add(lookup)
            session.flush()
            session.add(TransitPlanet(
                transit_lookup_id=lookup.id,
                planet="Mercury",
                degree=5, minutes=0, seconds=0.0,
                sign=mercury_sign,
                absolute_position=5.0,
                is_retrograde=False,
                calculation_method="pysweph",
            ))
        session.commit()

    return profile


def test_get_transit_history_all(db_helper, temp_db):
    """get_transit_history returns all rows when no filters applied."""
    _db_path, engine = temp_db
    profile = _make_profile_with_transits(db_helper, engine)

    rows = db_helper.get_transit_history(profile, limit=10)
    assert len(rows) == 2
    # Newest first
    assert rows[0]["lookup_datetime"] > rows[1]["lookup_datetime"]


def test_get_transit_history_date_filter(db_helper, temp_db):
    """get_transit_history respects after/before date filters."""
    _db_path, engine = temp_db
    profile = _make_profile_with_transits(db_helper, engine)

    rows = db_helper.get_transit_history(profile, after="2026-01-15", limit=10)
    assert len(rows) == 1
    assert "2026-02" in rows[0]["lookup_datetime"]


def test_get_transit_history_planet_sign_filter(db_helper, temp_db):
    """get_transit_history filters by planet and sign correctly."""
    _db_path, engine = temp_db
    profile = _make_profile_with_transits(db_helper, engine)

    rows = db_helper.get_transit_history(
        profile, planet="Mercury", sign="Capricorn", limit=10
    )
    assert len(rows) == 1
    assert rows[0]["planets"]["Mercury"]["sign"] == "Capricorn"


def test_get_transit_history_limit(db_helper, temp_db):
    """get_transit_history respects the limit parameter."""
    _db_path, engine = temp_db
    profile = _make_profile_with_transits(db_helper, engine)

    rows = db_helper.get_transit_history(profile, limit=1)
    assert len(rows) == 1


def test_find_last_transit_by_sign(db_helper, temp_db):
    """find_last_transit returns the most recent match for planet+sign."""
    _db_path, engine = temp_db
    profile = _make_profile_with_transits(db_helper, engine)

    result = db_helper.find_last_transit(profile, planet="Mercury", sign="Aquarius")
    assert result is not None
    assert result["sign"] == "Aquarius"
    assert result["planet"] == "Mercury"
    assert "2026-02" in result["lookup_datetime"]


def test_find_last_transit_by_sign_no_match(db_helper, temp_db):
    """find_last_transit returns None when no match exists."""
    _db_path, engine = temp_db
    profile = _make_profile_with_transits(db_helper, engine)

    result = db_helper.find_last_transit(profile, planet="Mercury", sign="Scorpio")
    assert result is None


def test_find_last_transit_by_retrograde(db_helper, temp_db):
    """find_last_transit matches on retrograde flag."""
    from datetime import datetime
    from w8s_astro_mcp.models import TransitLookup, TransitPlanet, Location
    from w8s_astro_mcp.database import get_session

    _db_path, engine = temp_db
    profile = db_helper.create_profile_with_location(
        name="Retro Test",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago",
    )

    with get_session(engine) as session:
        loc = session.query(Location).filter_by(profile_id=profile.id).first()
        lookup = TransitLookup(
            profile_id=profile.id,
            location_id=loc.id,
            house_system_id=1,
            lookup_datetime=datetime.fromisoformat("2026-01-10T12:00:00"),
            location_snapshot_label=loc.label,
            location_snapshot_latitude=loc.latitude,
            location_snapshot_longitude=loc.longitude,
            location_snapshot_timezone=loc.timezone,
        )
        session.add(lookup)
        session.flush()
        session.add(TransitPlanet(
            transit_lookup_id=lookup.id,
            planet="Mercury",
            degree=12, minutes=0, seconds=0.0,
            sign="Capricorn",
            absolute_position=282.0,
            is_retrograde=True,
            calculation_method="pysweph",
        ))
        session.commit()

    result = db_helper.find_last_transit(profile, planet="Mercury", retrograde=True)
    assert result is not None
    assert result["is_retrograde"] is True

    result_direct = db_helper.find_last_transit(profile, planet="Mercury", retrograde=False)
    assert result_direct is None
