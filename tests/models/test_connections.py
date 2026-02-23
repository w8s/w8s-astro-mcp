"""Tests for Phase 7 Connection models.

Covers all 6 connection models:
- Connection: root entity
- ConnectionMember: junction table (connection ↔ profiles)
- ConnectionChart: cached chart per type per connection
- ConnectionPlanet: planet positions in connection chart
- ConnectionHouse: house cusps in connection chart
- ConnectionPoint: special points (ASC, MC) in connection chart

Test coverage per model:
- CREATE: valid data, constraint violations, null checks
- READ: by ID, filtering, not found
- UPDATE: field changes, constraint violations
- DELETE: direct delete, cascade behavior
- to_dict(): all fields present, correct values
- Edge cases: unique constraints, FK restrictions
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from w8s_astro_mcp.models import (
    Connection,
    ConnectionMember,
    ConnectionChart,
    ConnectionPlanet,
    ConnectionHouse,
    ConnectionPoint,
    Profile,
    Location,
    HouseSystem,
    HOUSE_SYSTEM_SEED_DATA,
)


# =============================================================================
# SHARED FIXTURES
# =============================================================================

@pytest.fixture
def house_system(test_session):
    """Single seeded Placidus house system."""
    hs = HouseSystem(**HOUSE_SYSTEM_SEED_DATA[0])  # Placidus
    test_session.add(hs)
    test_session.commit()
    return hs


@pytest.fixture
def two_profiles(test_session, house_system):
    """Two profiles for connection tests."""
    loc_a = Location(label="St. Louis, MO", latitude=38.627, longitude=-90.198, timezone="America/Chicago")
    loc_b = Location(label="Chicago, IL", latitude=41.878, longitude=-87.629, timezone="America/Chicago")
    test_session.add_all([loc_a, loc_b])
    test_session.flush()

    profile_a = Profile(name="Alice", birth_date="1990-03-15", birth_time="14:30",
                        birth_location_id=loc_a.id, preferred_house_system_id=house_system.id)
    profile_b = Profile(name="Bob", birth_date="1988-07-22", birth_time="08:45",
                        birth_location_id=loc_b.id, preferred_house_system_id=house_system.id)
    test_session.add_all([profile_a, profile_b])
    test_session.commit()
    return profile_a, profile_b


@pytest.fixture
def basic_connection(test_session):
    """A simple connection with no members yet."""
    conn = Connection(label="Alice & Bob", type="romantic")
    test_session.add(conn)
    test_session.commit()
    return conn


@pytest.fixture
def connection_with_members(test_session, basic_connection, two_profiles):
    """Connection with two members added."""
    profile_a, profile_b = two_profiles
    member_a = ConnectionMember(connection_id=basic_connection.id, profile_id=profile_a.id)
    member_b = ConnectionMember(connection_id=basic_connection.id, profile_id=profile_b.id)
    test_session.add_all([member_a, member_b])
    test_session.commit()
    return basic_connection, profile_a, profile_b


@pytest.fixture
def composite_chart(test_session, connection_with_members):
    """A composite ConnectionChart for the connection."""
    conn, _, _ = connection_with_members
    chart = ConnectionChart(
        connection_id=conn.id,
        chart_type="composite",
        is_valid=True,
        calculated_at=datetime.now(timezone.utc),
        calculation_method="swetest",
        ephemeris_version="2.10"
    )
    test_session.add(chart)
    test_session.commit()
    return chart


@pytest.fixture
def davison_chart(test_session, connection_with_members):
    """A Davison ConnectionChart for the connection."""
    conn, _, _ = connection_with_members
    chart = ConnectionChart(
        connection_id=conn.id,
        chart_type="davison",
        davison_date="1989-05-18",
        davison_time="11:37",
        davison_latitude=40.0,
        davison_longitude=-88.0,
        davison_timezone="America/Chicago",
        is_valid=True,
        calculated_at=datetime.now(timezone.utc),
        calculation_method="swetest",
        ephemeris_version="2.10"
    )
    test_session.add(chart)
    test_session.commit()
    return chart


# =============================================================================
# CONNECTION TESTS
# =============================================================================

class TestConnectionCreate:
    """Test creating Connection records."""

    def test_create_minimal(self, test_session):
        """Should create with just a label (all other fields optional)."""
        conn = Connection(label="Test Connection")
        test_session.add(conn)
        test_session.commit()

        assert conn.id is not None
        assert conn.label == "Test Connection"
        assert conn.type is None
        assert conn.start_date is None
        assert conn.created_at is not None
        assert conn.updated_at is not None

    def test_create_full(self, test_session):
        """Should create with all fields."""
        conn = Connection(label="Alice & Bob", type="romantic", start_date="2020-06-15")
        test_session.add(conn)
        test_session.commit()

        assert conn.label == "Alice & Bob"
        assert conn.type == "romantic"
        assert conn.start_date == "2020-06-15"

    def test_create_without_label_fails(self, test_session):
        """Should fail when label is missing."""
        conn = Connection(type="romantic")
        test_session.add(conn)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_create_multiple_connections(self, test_session):
        """Should allow multiple connections with same type."""
        conn_a = Connection(label="Couple A", type="romantic")
        conn_b = Connection(label="Couple B", type="romantic")
        test_session.add_all([conn_a, conn_b])
        test_session.commit()

        assert test_session.query(Connection).count() == 2


class TestConnectionRead:
    """Test reading Connection records."""

    def test_read_by_id(self, test_session, basic_connection):
        result = test_session.query(Connection).filter_by(id=basic_connection.id).first()
        assert result is not None
        assert result.label == "Alice & Bob"

    def test_read_by_type(self, test_session):
        test_session.add(Connection(label="A", type="romantic"))
        test_session.add(Connection(label="B", type="family"))
        test_session.commit()

        romantic = test_session.query(Connection).filter_by(type="romantic").all()
        assert len(romantic) == 1
        assert romantic[0].label == "A"

    def test_read_nonexistent(self, test_session):
        result = test_session.query(Connection).filter_by(id=99999).first()
        assert result is None


class TestConnectionDelete:
    """Test deleting Connection records."""

    def test_delete_connection(self, test_session, basic_connection):
        test_session.delete(basic_connection)
        test_session.commit()
        assert test_session.query(Connection).filter_by(id=basic_connection.id).first() is None

    def test_delete_cascades_to_members(self, test_session, connection_with_members):
        conn, profile_a, profile_b = connection_with_members
        conn_id = conn.id

        test_session.delete(conn)
        test_session.commit()

        remaining = test_session.query(ConnectionMember).filter_by(connection_id=conn_id).all()
        assert len(remaining) == 0

    def test_delete_cascades_to_charts(self, test_session, composite_chart, connection_with_members):
        conn, _, _ = connection_with_members
        chart_id = composite_chart.id
        conn_id = conn.id

        test_session.delete(conn)
        test_session.commit()

        assert test_session.query(ConnectionChart).filter_by(id=chart_id).first() is None


class TestConnectionToDict:
    """Test Connection.to_dict()."""

    def test_to_dict_all_fields(self, test_session, basic_connection):
        data = basic_connection.to_dict()
        assert all(k in data for k in ["id", "label", "type", "start_date", "created_at", "updated_at"])

    def test_to_dict_values(self, test_session, basic_connection):
        data = basic_connection.to_dict()
        assert data["label"] == "Alice & Bob"
        assert data["type"] == "romantic"


# =============================================================================
# CONNECTION MEMBER TESTS
# =============================================================================

class TestConnectionMemberCreate:
    """Test creating ConnectionMember records."""

    def test_create_member(self, test_session, basic_connection, two_profiles):
        profile_a, _ = two_profiles
        member = ConnectionMember(connection_id=basic_connection.id, profile_id=profile_a.id)
        test_session.add(member)
        test_session.commit()

        assert member.id is not None
        assert member.connection_id == basic_connection.id
        assert member.profile_id == profile_a.id

    def test_duplicate_member_fails(self, test_session, connection_with_members):
        conn, profile_a, _ = connection_with_members
        duplicate = ConnectionMember(connection_id=conn.id, profile_id=profile_a.id)
        test_session.add(duplicate)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_same_profile_in_different_connections(self, test_session, two_profiles, house_system):
        profile_a, _ = two_profiles
        conn1 = Connection(label="Connection 1")
        conn2 = Connection(label="Connection 2")
        test_session.add_all([conn1, conn2])
        test_session.flush()

        m1 = ConnectionMember(connection_id=conn1.id, profile_id=profile_a.id)
        m2 = ConnectionMember(connection_id=conn2.id, profile_id=profile_a.id)
        test_session.add_all([m1, m2])
        test_session.commit()  # Should not raise

        assert test_session.query(ConnectionMember).filter_by(profile_id=profile_a.id).count() == 2

    def test_delete_profile_restricted_when_member(self, test_session, connection_with_members):
        """Cannot delete a profile that is a connection member (RESTRICT)."""
        conn, profile_a, _ = connection_with_members
        test_session.delete(profile_a)
        with pytest.raises(IntegrityError):
            test_session.commit()


class TestConnectionMemberToDict:
    def test_to_dict(self, test_session, connection_with_members):
        conn, profile_a, _ = connection_with_members
        member = test_session.query(ConnectionMember).filter_by(
            connection_id=conn.id, profile_id=profile_a.id
        ).first()
        data = member.to_dict()
        assert data["connection_id"] == conn.id
        assert data["profile_id"] == profile_a.id


# =============================================================================
# CONNECTION CHART TESTS
# =============================================================================

class TestConnectionChartCreate:
    """Test creating ConnectionChart records."""

    def test_create_composite_chart(self, test_session, connection_with_members):
        conn, _, _ = connection_with_members
        chart = ConnectionChart(
            connection_id=conn.id,
            chart_type="composite",
            is_valid=True
        )
        test_session.add(chart)
        test_session.commit()

        assert chart.id is not None
        assert chart.chart_type == "composite"
        assert chart.is_valid is True
        assert chart.davison_date is None

    def test_create_davison_chart(self, test_session, davison_chart):
        assert davison_chart.chart_type == "davison"
        assert davison_chart.davison_date == "1989-05-18"
        assert davison_chart.davison_latitude == 40.0

    def test_duplicate_chart_type_fails(self, test_session, composite_chart, connection_with_members):
        conn, _, _ = connection_with_members
        duplicate = ConnectionChart(connection_id=conn.id, chart_type="composite", is_valid=True)
        test_session.add(duplicate)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_composite_and_davison_coexist(self, test_session, composite_chart, davison_chart):
        """One composite and one Davison chart can coexist for the same connection."""
        # Both fixtures share the same connection via connection_with_members
        # Just verify they're both queryable
        assert composite_chart.chart_type == "composite"
        assert davison_chart.chart_type == "davison"

    def test_is_valid_defaults_true(self, test_session, connection_with_members):
        conn, _, _ = connection_with_members
        chart = ConnectionChart(connection_id=conn.id, chart_type="composite")
        test_session.add(chart)
        test_session.commit()
        assert chart.is_valid is True

    def test_invalidate_chart(self, test_session, composite_chart):
        composite_chart.is_valid = False
        test_session.commit()

        refreshed = test_session.query(ConnectionChart).filter_by(id=composite_chart.id).first()
        assert refreshed.is_valid is False


class TestConnectionChartToDict:
    def test_to_dict_composite(self, test_session, composite_chart):
        data = composite_chart.to_dict()
        assert all(k in data for k in [
            "id", "connection_id", "chart_type", "is_valid",
            "davison_date", "davison_time", "davison_latitude",
            "davison_longitude", "davison_timezone",
            "calculated_at", "calculation_method", "ephemeris_version"
        ])
        assert data["chart_type"] == "composite"
        assert data["davison_date"] is None

    def test_to_dict_davison(self, test_session, davison_chart):
        data = davison_chart.to_dict()
        assert data["chart_type"] == "davison"
        assert data["davison_date"] == "1989-05-18"
        assert data["davison_latitude"] == 40.0


# =============================================================================
# CONNECTION PLANET TESTS
# =============================================================================

class TestConnectionPlanetCreate:
    """Test creating ConnectionPlanet records."""

    def test_create_planet(self, test_session, composite_chart):
        planet = ConnectionPlanet(
            connection_chart_id=composite_chart.id,
            planet="Sun",
            degree=15, minutes=24, seconds=36.0,
            sign="Taurus",
            absolute_position=45.41,
            is_retrograde=False,
            calculation_method="swetest"
        )
        test_session.add(planet)
        test_session.commit()

        assert planet.id is not None
        assert planet.planet == "Sun"
        assert planet.sign == "Taurus"
        assert planet.absolute_position == 45.41

    def test_duplicate_planet_in_chart_fails(self, test_session, composite_chart):
        sun1 = ConnectionPlanet(
            connection_chart_id=composite_chart.id, planet="Sun",
            degree=15, minutes=0, seconds=0.0, sign="Taurus",
            absolute_position=45.0, is_retrograde=False, calculation_method="swetest"
        )
        sun2 = ConnectionPlanet(
            connection_chart_id=composite_chart.id, planet="Sun",
            degree=20, minutes=0, seconds=0.0, sign="Gemini",
            absolute_position=80.0, is_retrograde=False, calculation_method="swetest"
        )
        test_session.add_all([sun1, sun2])
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_same_planet_in_different_charts(self, test_session, composite_chart, davison_chart):
        sun_composite = ConnectionPlanet(
            connection_chart_id=composite_chart.id, planet="Sun",
            degree=15, minutes=0, seconds=0.0, sign="Taurus",
            absolute_position=45.0, is_retrograde=False, calculation_method="swetest"
        )
        sun_davison = ConnectionPlanet(
            connection_chart_id=davison_chart.id, planet="Sun",
            degree=20, minutes=0, seconds=0.0, sign="Gemini",
            absolute_position=80.0, is_retrograde=False, calculation_method="swetest"
        )
        test_session.add_all([sun_composite, sun_davison])
        test_session.commit()  # Should not raise

    def test_delete_chart_cascades_to_planets(self, test_session, composite_chart):
        planet = ConnectionPlanet(
            connection_chart_id=composite_chart.id, planet="Moon",
            degree=5, minutes=0, seconds=0.0, sign="Aries",
            absolute_position=5.0, is_retrograde=False, calculation_method="swetest"
        )
        test_session.add(planet)
        test_session.commit()
        chart_id = composite_chart.id

        test_session.delete(composite_chart)
        test_session.commit()

        remaining = test_session.query(ConnectionPlanet).filter_by(connection_chart_id=chart_id).all()
        assert len(remaining) == 0

    def test_formatted_position(self, test_session, composite_chart):
        planet = ConnectionPlanet(
            connection_chart_id=composite_chart.id, planet="Venus",
            degree=10, minutes=30, seconds=15.0, sign="Libra",
            absolute_position=190.5, is_retrograde=False, calculation_method="swetest"
        )
        test_session.add(planet)
        test_session.commit()
        assert planet.formatted_position == "10°30'15\" Libra"

    def test_to_dict(self, test_session, composite_chart):
        planet = ConnectionPlanet(
            connection_chart_id=composite_chart.id, planet="Mars",
            degree=3, minutes=12, seconds=0.0, sign="Scorpio",
            absolute_position=213.2, is_retrograde=True, calculation_method="swetest"
        )
        test_session.add(planet)
        test_session.commit()
        data = planet.to_dict()
        assert all(k in data for k in [
            "id", "connection_chart_id", "planet", "degree", "minutes", "seconds",
            "sign", "absolute_position", "house_number", "is_retrograde",
            "calculated_at", "calculation_method", "ephemeris_version"
        ])
        assert data["planet"] == "Mars"
        assert data["is_retrograde"] is True


# =============================================================================
# CONNECTION HOUSE TESTS
# =============================================================================

class TestConnectionHouseCreate:
    """Test creating ConnectionHouse records."""

    def test_create_house(self, test_session, composite_chart, house_system):
        house = ConnectionHouse(
            connection_chart_id=composite_chart.id,
            house_system_id=house_system.id,
            house_number=1,
            degree=5, minutes=30, seconds=0.0,
            sign="Aries",
            absolute_position=5.5,
            calculation_method="swetest"
        )
        test_session.add(house)
        test_session.commit()

        assert house.id is not None
        assert house.house_number == 1
        assert house.sign == "Aries"

    def test_duplicate_house_number_fails(self, test_session, composite_chart, house_system):
        house1 = ConnectionHouse(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            house_number=1, degree=5, minutes=0, seconds=0.0,
            sign="Aries", absolute_position=5.0, calculation_method="swetest"
        )
        house2 = ConnectionHouse(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            house_number=1, degree=10, minutes=0, seconds=0.0,
            sign="Taurus", absolute_position=40.0, calculation_method="swetest"
        )
        test_session.add_all([house1, house2])
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_create_all_12_houses(self, test_session, composite_chart, house_system):
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        for i, sign in enumerate(signs, start=1):
            house = ConnectionHouse(
                connection_chart_id=composite_chart.id, house_system_id=house_system.id,
                house_number=i, degree=0, minutes=0, seconds=0.0,
                sign=sign, absolute_position=float((i - 1) * 30),
                calculation_method="swetest"
            )
            test_session.add(house)
        test_session.commit()

        count = test_session.query(ConnectionHouse).filter_by(
            connection_chart_id=composite_chart.id
        ).count()
        assert count == 12

    def test_to_dict(self, test_session, composite_chart, house_system):
        house = ConnectionHouse(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            house_number=10, degree=9, minutes=20, seconds=0.0,
            sign="Capricorn", absolute_position=279.33, calculation_method="swetest"
        )
        test_session.add(house)
        test_session.commit()
        data = house.to_dict()
        assert all(k in data for k in [
            "id", "connection_chart_id", "house_system_id", "house_number",
            "degree", "minutes", "seconds", "sign", "absolute_position",
            "calculated_at", "calculation_method", "ephemeris_version"
        ])
        assert data["house_number"] == 10


# =============================================================================
# CONNECTION POINT TESTS
# =============================================================================

class TestConnectionPointCreate:
    """Test creating ConnectionPoint records."""

    def test_create_asc(self, test_session, composite_chart, house_system):
        point = ConnectionPoint(
            connection_chart_id=composite_chart.id,
            house_system_id=house_system.id,
            point_type="ASC",
            degree=5, minutes=30, seconds=0.0,
            sign="Aries",
            absolute_position=5.5,
            calculation_method="swetest"
        )
        test_session.add(point)
        test_session.commit()

        assert point.id is not None
        assert point.point_type == "ASC"

    def test_create_mc(self, test_session, composite_chart, house_system):
        point = ConnectionPoint(
            connection_chart_id=composite_chart.id,
            house_system_id=house_system.id,
            point_type="MC",
            degree=9, minutes=20, seconds=0.0,
            sign="Capricorn",
            absolute_position=279.33,
            calculation_method="swetest"
        )
        test_session.add(point)
        test_session.commit()
        assert point.point_type == "MC"

    def test_duplicate_point_type_fails(self, test_session, composite_chart, house_system):
        asc1 = ConnectionPoint(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            point_type="ASC", degree=5, minutes=0, seconds=0.0,
            sign="Aries", absolute_position=5.0, calculation_method="swetest"
        )
        asc2 = ConnectionPoint(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            point_type="ASC", degree=10, minutes=0, seconds=0.0,
            sign="Taurus", absolute_position=40.0, calculation_method="swetest"
        )
        test_session.add_all([asc1, asc2])
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_asc_and_mc_coexist(self, test_session, composite_chart, house_system):
        asc = ConnectionPoint(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            point_type="ASC", degree=5, minutes=0, seconds=0.0,
            sign="Aries", absolute_position=5.0, calculation_method="swetest"
        )
        mc = ConnectionPoint(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            point_type="MC", degree=9, minutes=0, seconds=0.0,
            sign="Capricorn", absolute_position=279.0, calculation_method="swetest"
        )
        test_session.add_all([asc, mc])
        test_session.commit()  # Should not raise

        count = test_session.query(ConnectionPoint).filter_by(
            connection_chart_id=composite_chart.id
        ).count()
        assert count == 2

    def test_formatted_position(self, test_session, composite_chart, house_system):
        point = ConnectionPoint(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            point_type="ASC", degree=12, minutes=45, seconds=30.0,
            sign="Leo", absolute_position=132.75, calculation_method="swetest"
        )
        test_session.add(point)
        test_session.commit()
        assert point.formatted_position == "12°45'30\" Leo"

    def test_to_dict(self, test_session, composite_chart, house_system):
        point = ConnectionPoint(
            connection_chart_id=composite_chart.id, house_system_id=house_system.id,
            point_type="ASC", degree=5, minutes=0, seconds=0.0,
            sign="Aries", absolute_position=5.0, calculation_method="swetest"
        )
        test_session.add(point)
        test_session.commit()
        data = point.to_dict()
        assert all(k in data for k in [
            "id", "connection_chart_id", "house_system_id", "point_type",
            "degree", "minutes", "seconds", "sign", "absolute_position",
            "calculated_at", "calculation_method", "ephemeris_version"
        ])
        assert data["point_type"] == "ASC"


# =============================================================================
# FULL CASCADE CHAIN TEST
# =============================================================================

class TestCascadeChain:
    """Test the full cascade: Connection → Chart → Planet/House/Point."""

    def test_delete_connection_cascades_all(self, test_session, composite_chart, house_system, connection_with_members):
        conn, _, _ = connection_with_members
        chart_id = composite_chart.id

        # Add planet, house, point to the chart
        planet = ConnectionPlanet(
            connection_chart_id=chart_id, planet="Sun",
            degree=15, minutes=0, seconds=0.0, sign="Taurus",
            absolute_position=45.0, is_retrograde=False, calculation_method="swetest"
        )
        house = ConnectionHouse(
            connection_chart_id=chart_id, house_system_id=house_system.id,
            house_number=1, degree=5, minutes=0, seconds=0.0,
            sign="Aries", absolute_position=5.0, calculation_method="swetest"
        )
        point = ConnectionPoint(
            connection_chart_id=chart_id, house_system_id=house_system.id,
            point_type="ASC", degree=5, minutes=0, seconds=0.0,
            sign="Aries", absolute_position=5.0, calculation_method="swetest"
        )
        test_session.add_all([planet, house, point])
        test_session.commit()

        # Delete the connection
        test_session.delete(conn)
        test_session.commit()

        # Everything should be gone
        assert test_session.query(ConnectionChart).filter_by(id=chart_id).first() is None
        assert test_session.query(ConnectionPlanet).filter_by(connection_chart_id=chart_id).count() == 0
        assert test_session.query(ConnectionHouse).filter_by(connection_chart_id=chart_id).count() == 0
        assert test_session.query(ConnectionPoint).filter_by(connection_chart_id=chart_id).count() == 0
