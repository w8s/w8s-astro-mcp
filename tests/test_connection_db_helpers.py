"""Integration tests for connection db_helper methods (Phase 7).

Uses a real DatabaseHelper against an in-memory SQLite database.
Tests the full round-trip: Python → SQLAlchemy → SQLite → Python.

Coverage:
- create_connection
- list_all_connections
- get_connection_by_id
- get_connection_members
- add_connection_member
- remove_connection_member
- delete_connection
- get_connection_chart (no chart → None)
- invalidate_connection_charts
- save_connection_chart (composite format + swetest format)
- get_connection_planets / get_connection_houses / get_connection_points
- _normalize_position (both input formats)
"""

import os
import tempfile
import pytest
from datetime import datetime, timezone
from pathlib import Path

from w8s_astro_mcp.database import create_db_engine, create_tables
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper
from w8s_astro_mcp.models import (
    HouseSystem, HOUSE_SYSTEM_SEED_DATA,
    Profile, Location,
    Connection, ConnectionChart,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db(tmp_path):
    """DatabaseHelper backed by a fresh temp SQLite file.

    Imports all models before construction so Base.metadata is fully
    populated and create_tables() creates every table.
    """
    # Must import all models before DatabaseHelper creates tables
    from w8s_astro_mcp.models import (  # noqa: F401
        HouseSystem, Location, Profile,
        NatalPlanet, NatalHouse, NatalPoint,
        TransitLookup, TransitPlanet, TransitHouse, TransitPoint,
        Connection, ConnectionMember, ConnectionChart,
        ConnectionPlanet, ConnectionHouse, ConnectionPoint,
    )

    db_path = tmp_path / "test_connections.db"
    helper = DatabaseHelper(db_path=str(db_path))

    # Seed house systems (required for save_connection_chart)
    from w8s_astro_mcp.database import get_session
    with get_session(helper.engine) as session:
        for data in HOUSE_SYSTEM_SEED_DATA:
            session.add(HouseSystem(**data))
        session.commit()

    return helper


@pytest.fixture(scope="function")
def two_profiles(db):
    """Two profiles with birth locations for connection tests."""
    alice = db.create_profile_with_location(
        name="Alice",
        birth_date="1990-03-15",
        birth_time="14:30",
        birth_location_name="St. Louis, MO",
        birth_latitude=38.627,
        birth_longitude=-90.198,
        birth_timezone="America/Chicago",
    )
    bob = db.create_profile_with_location(
        name="Bob",
        birth_date="1988-07-22",
        birth_time="08:45",
        birth_location_name="Chicago, IL",
        birth_latitude=41.878,
        birth_longitude=-87.629,
        birth_timezone="America/Chicago",
    )
    return alice, bob


@pytest.fixture(scope="function")
def basic_connection(db, two_profiles):
    """A connection with two members."""
    alice, bob = two_profiles
    return db.create_connection(
        label="Alice & Bob",
        profile_ids=[alice.id, bob.id],
        type="romantic",
    )


# Minimal position dicts in both supported formats
COMPOSITE_POSITIONS = {
    "planets": {
        "Sun": {"sign": "Gemini", "degree": 15, "minutes": 24, "seconds": 36.0,
                "absolute_position": 75.41},
        "Moon": {"sign": "Scorpio", "degree": 8, "minutes": 0, "seconds": 0.0,
                 "absolute_position": 218.0},
    },
    "houses": {
        "1": {"sign": "Aries", "degree": 5, "minutes": 0, "seconds": 0.0,
              "absolute_position": 5.0},
    },
    "points": {
        "ASC": {"sign": "Aries", "degree": 5, "minutes": 0, "seconds": 0.0,
                "absolute_position": 5.0},
    },
}

SWETEST_POSITIONS = {
    "planets": {
        "Sun": {"sign": "Aquarius", "degree": 14.66, "formatted": "14°39'36\""},
    },
    "houses": {
        "1": {"sign": "Taurus", "degree": 2.5},
    },
    "points": {
        "ASC": {"sign": "Taurus", "degree": 2.5},
    },
}


# =============================================================================
# _normalize_position
# =============================================================================

class TestNormalizePosition:

    def test_composite_format_passthrough(self, db):
        """Composite data already has all fields — should pass through unchanged."""
        data = {"sign": "Gemini", "degree": 15, "minutes": 24,
                "seconds": 36.0, "absolute_position": 75.41}
        n = db._normalize_position(data)
        assert n["degree"] == 15
        assert n["minutes"] == 24
        assert abs(n["seconds"] - 36.0) < 0.01
        assert abs(n["absolute_position"] - 75.41) < 0.001

    def test_swetest_format_derives_dms(self, db):
        """Swetest decimal degree gets split into int degree/minutes/seconds."""
        data = {"sign": "Aquarius", "degree": 14.66}
        n = db._normalize_position(data)
        assert n["degree"] == 14
        assert n["minutes"] == 39
        assert abs(n["seconds"] - 36.0) < 0.1

    def test_swetest_format_derives_absolute_position(self, db):
        """Swetest data gets absolute_position from sign + degree."""
        data = {"sign": "Aquarius", "degree": 14.66}
        n = db._normalize_position(data)
        # Aquarius = 300°, 14.66° in = 314.66°
        assert abs(n["absolute_position"] - 314.66) < 0.001

    def test_does_not_mutate_input(self, db):
        """Input dict should not be modified."""
        data = {"sign": "Aries", "degree": 5.0}
        original = dict(data)
        db._normalize_position(data)
        assert data == original

    def test_all_12_signs(self, db):
        """Each sign produces the correct absolute_position offset."""
        sign_offsets = {
            "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90,
            "Leo": 120, "Virgo": 150, "Libra": 180, "Scorpio": 210,
            "Sagittarius": 240, "Capricorn": 270, "Aquarius": 300, "Pisces": 330,
        }
        for sign, offset in sign_offsets.items():
            n = db._normalize_position({"sign": sign, "degree": 0.0})
            assert abs(n["absolute_position"] - offset) < 0.001, f"{sign}: expected {offset}"

    def test_unknown_sign_raises(self, db):
        """Unknown sign name should propagate ValueError from position_utils."""
        with pytest.raises(ValueError, match="Unknown sign"):
            db._normalize_position({"sign": "Ophiuchus", "degree": 5.0})


# =============================================================================
# create_connection
# =============================================================================

class TestCreateConnection:

    def test_creates_with_label_and_members(self, db, two_profiles):
        alice, bob = two_profiles
        conn = db.create_connection(label="Test", profile_ids=[alice.id, bob.id])
        assert conn.id is not None
        assert conn.label == "Test"

    def test_creates_with_optional_fields(self, db, two_profiles):
        alice, bob = two_profiles
        conn = db.create_connection(
            label="Couple", profile_ids=[alice.id, bob.id],
            type="romantic", start_date="2020-06-15"
        )
        assert conn.type == "romantic"
        assert conn.start_date == "2020-06-15"

    def test_members_are_linked(self, db, two_profiles):
        alice, bob = two_profiles
        conn = db.create_connection(label="Test", profile_ids=[alice.id, bob.id])
        members = db.get_connection_members(conn)
        assert len(members) == 2
        names = {m.name for m in members}
        assert names == {"Alice", "Bob"}

    def test_three_members(self, db, two_profiles):
        alice, bob = two_profiles
        carol = db.create_profile_with_location(
            name="Carol", birth_date="1992-01-01", birth_time="12:00",
            birth_location_name="NYC", birth_latitude=40.71, birth_longitude=-74.0,
            birth_timezone="America/New_York",
        )
        conn = db.create_connection(label="Trio", profile_ids=[alice.id, bob.id, carol.id])
        members = db.get_connection_members(conn)
        assert len(members) == 3


# =============================================================================
# list_all_connections / get_connection_by_id
# =============================================================================

class TestListAndGet:

    def test_list_empty(self, db):
        assert db.list_all_connections() == []

    def test_list_returns_all(self, db, two_profiles):
        alice, bob = two_profiles
        db.create_connection(label="A", profile_ids=[alice.id, bob.id])
        db.create_connection(label="B", profile_ids=[alice.id, bob.id])
        assert len(db.list_all_connections()) == 2

    def test_get_by_id(self, db, basic_connection):
        found = db.get_connection_by_id(basic_connection.id)
        assert found is not None
        assert found.label == "Alice & Bob"

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_connection_by_id(99999) is None


# =============================================================================
# add_connection_member / remove_connection_member
# =============================================================================

class TestMemberManagement:

    def test_add_member(self, db, basic_connection, two_profiles):
        alice, bob = two_profiles
        carol = db.create_profile_with_location(
            name="Carol", birth_date="1992-01-01", birth_time="12:00",
            birth_location_name="NYC", birth_latitude=40.71, birth_longitude=-74.0,
            birth_timezone="America/New_York",
        )
        db.add_connection_member(basic_connection.id, carol.id)
        members = db.get_connection_members(basic_connection)
        assert len(members) == 3

    def test_remove_member(self, db, basic_connection, two_profiles):
        alice, bob = two_profiles
        carol = db.create_profile_with_location(
            name="Carol", birth_date="1992-01-01", birth_time="12:00",
            birth_location_name="NYC", birth_latitude=40.71, birth_longitude=-74.0,
            birth_timezone="America/New_York",
        )
        db.add_connection_member(basic_connection.id, carol.id)
        db.remove_connection_member(basic_connection.id, carol.id)
        members = db.get_connection_members(basic_connection)
        assert len(members) == 2
        assert all(m.name != "Carol" for m in members)

    def test_duplicate_member_raises(self, db, basic_connection, two_profiles):
        from w8s_astro_mcp.database import DatabaseError
        alice, _ = two_profiles
        with pytest.raises(DatabaseError):
            db.add_connection_member(basic_connection.id, alice.id)


# =============================================================================
# delete_connection
# =============================================================================

class TestDeleteConnection:

    def test_delete_removes_connection(self, db, basic_connection):
        conn_id = basic_connection.id
        result = db.delete_connection(conn_id)
        assert result is True
        assert db.get_connection_by_id(conn_id) is None

    def test_delete_nonexistent_returns_false(self, db):
        assert db.delete_connection(99999) is False

    def test_delete_does_not_remove_profiles(self, db, basic_connection, two_profiles):
        alice, bob = two_profiles
        db.delete_connection(basic_connection.id)
        assert db.get_profile_by_id(alice.id) is not None
        assert db.get_profile_by_id(bob.id) is not None


# =============================================================================
# save_connection_chart / get_connection_chart
# =============================================================================

class TestSaveAndGetChart:

    def test_get_chart_returns_none_before_save(self, db, basic_connection):
        assert db.get_connection_chart(basic_connection.id, "composite") is None

    def test_save_composite_chart(self, db, basic_connection):
        chart = db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="composite",
            positions=COMPOSITE_POSITIONS,
            calculation_method="circular_mean",
        )
        assert chart.id is not None
        assert chart.chart_type == "composite"
        assert chart.is_valid is True

    def test_save_davison_chart(self, db, basic_connection):
        midpoint = {
            "date": "1989-05-18", "time": "11:37",
            "latitude": 40.25, "longitude": -88.91, "timezone": "UTC",
        }
        chart = db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="davison",
            positions=COMPOSITE_POSITIONS,
            davison_midpoint=midpoint,
            calculation_method="swetest",
        )
        assert chart.davison_date == "1989-05-18"
        assert abs(chart.davison_latitude - 40.25) < 0.001

    def test_save_swetest_format(self, db, basic_connection):
        """Saving swetest-format positions should not raise."""
        chart = db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="composite",
            positions=SWETEST_POSITIONS,
        )
        assert chart.is_valid is True

    def test_get_chart_after_save(self, db, basic_connection):
        db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="composite",
            positions=COMPOSITE_POSITIONS,
        )
        chart = db.get_connection_chart(basic_connection.id, "composite")
        assert chart is not None
        assert chart.chart_type == "composite"

    def test_save_upserts_on_recalculate(self, db, basic_connection):
        """Saving twice should update the existing row, not create a duplicate."""
        db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="composite",
            positions=COMPOSITE_POSITIONS,
        )
        db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="composite",
            positions=COMPOSITE_POSITIONS,
        )
        from w8s_astro_mcp.database import get_session
        with get_session(db.engine) as session:
            count = session.query(ConnectionChart).filter_by(
                connection_id=basic_connection.id, chart_type="composite"
            ).count()
        assert count == 1

    def test_composite_and_davison_coexist(self, db, basic_connection):
        db.save_connection_chart(
            connection_id=basic_connection.id, chart_type="composite",
            positions=COMPOSITE_POSITIONS,
        )
        db.save_connection_chart(
            connection_id=basic_connection.id, chart_type="davison",
            positions=COMPOSITE_POSITIONS,
        )
        assert db.get_connection_chart(basic_connection.id, "composite") is not None
        assert db.get_connection_chart(basic_connection.id, "davison") is not None


# =============================================================================
# invalidate_connection_charts
# =============================================================================

class TestInvalidateCharts:

    def test_invalidate_sets_is_valid_false(self, db, basic_connection):
        db.save_connection_chart(
            connection_id=basic_connection.id, chart_type="composite",
            positions=COMPOSITE_POSITIONS,
        )
        db.invalidate_connection_charts(basic_connection.id)
        chart = db.get_connection_chart(basic_connection.id, "composite")
        assert chart.is_valid is False

    def test_invalidate_all_chart_types(self, db, basic_connection):
        db.save_connection_chart(
            connection_id=basic_connection.id, chart_type="composite",
            positions=COMPOSITE_POSITIONS,
        )
        db.save_connection_chart(
            connection_id=basic_connection.id, chart_type="davison",
            positions=COMPOSITE_POSITIONS,
        )
        db.invalidate_connection_charts(basic_connection.id)
        for chart_type in ("composite", "davison"):
            chart = db.get_connection_chart(basic_connection.id, chart_type)
            assert chart.is_valid is False

    def test_invalidate_on_no_charts_is_noop(self, db, basic_connection):
        """Should not raise even when there are no charts to invalidate."""
        db.invalidate_connection_charts(basic_connection.id)  # no-op, no error


# =============================================================================
# get_connection_planets / houses / points
# =============================================================================

class TestGetChartRows:

    @pytest.fixture(autouse=True)
    def saved_chart(self, db, basic_connection):
        self.chart = db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="composite",
            positions=COMPOSITE_POSITIONS,
            calculation_method="circular_mean",
        )
        self.db = db

    def test_get_planets_count(self):
        planets = self.db.get_connection_planets(self.chart.id)
        assert len(planets) == 2

    def test_get_planets_names(self):
        planets = self.db.get_connection_planets(self.chart.id)
        names = {p.planet for p in planets}
        assert names == {"Sun", "Moon"}

    def test_planet_absolute_position(self):
        planets = self.db.get_connection_planets(self.chart.id)
        sun = next(p for p in planets if p.planet == "Sun")
        assert abs(sun.absolute_position - 75.41) < 0.01

    def test_planet_formatted_position(self):
        planets = self.db.get_connection_planets(self.chart.id)
        sun = next(p for p in planets if p.planet == "Sun")
        assert "Gemini" in sun.formatted_position
        assert "15" in sun.formatted_position

    def test_get_houses_count(self):
        houses = self.db.get_connection_houses(self.chart.id)
        assert len(houses) == 1

    def test_get_houses_ordered(self):
        houses = self.db.get_connection_houses(self.chart.id)
        assert houses[0].house_number == 1

    def test_get_points_count(self):
        points = self.db.get_connection_points(self.chart.id)
        assert len(points) == 1

    def test_get_points_type(self):
        points = self.db.get_connection_points(self.chart.id)
        assert points[0].point_type == "ASC"

    def test_swetest_format_saves_correctly(self, db, basic_connection):
        """Swetest-format positions should produce correct absolute_position in DB."""
        chart = db.save_connection_chart(
            connection_id=basic_connection.id,
            chart_type="davison",
            positions=SWETEST_POSITIONS,
        )
        planets = db.get_connection_planets(chart.id)
        sun = next(p for p in planets if p.planet == "Sun")
        # Aquarius (300°) + 14.66° = 314.66°
        assert abs(sun.absolute_position - 314.66) < 0.01
        assert sun.degree == 14
        assert sun.minutes == 39
