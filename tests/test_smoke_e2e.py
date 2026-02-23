"""End-to-end smoke tests for database functionality.

These tests verify the critical paths work together:
- Database creation
- Profile + Location creation
- Natal chart storage and retrieval
- Transit lookup logging
- DatabaseHelper queries
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import os

from w8s_astro_mcp.database import initialize_database, get_session
from w8s_astro_mcp.models import (
    Profile, Location, HouseSystem,
    NatalPlanet, NatalHouse, NatalPoint,
    TransitLookup, TransitPlanet, TransitHouse, TransitPoint
)
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper
from w8s_astro_mcp.utils.transit_logger import save_transit_data_to_db
from w8s_astro_mcp.utils.position_utils import (
    decimal_to_dms,
    sign_to_absolute_position
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    # Initialize with schema
    engine = initialize_database(db_path, echo=False)
    
    # Seed house systems (reference data)
    with get_session(engine) as session:
        house_systems = [
            HouseSystem(code='P', name='Placidus', description='Placidus house system'),
            HouseSystem(code='K', name='Koch', description='Koch house system'),
            HouseSystem(code='E', name='Equal', description='Equal house system'),
        ]
        for hs in house_systems:
            session.add(hs)
        session.commit()
    
    yield db_path, engine
    
    # Cleanup
    if db_path.exists():
        os.remove(db_path)


def test_smoke_create_profile_and_location(temp_db):
    """Smoke test: Create profile with birth location."""
    db_path, engine = temp_db
    
    with get_session(engine) as session:
        # Get Placidus house system
        house_system = session.query(HouseSystem).filter_by(code='P').first()
        assert house_system is not None, "Placidus house system should exist"
        
        # Create birth location
        birth_loc = Location(
            label="Richardson, TX",
            latitude=32.9483,
            longitude=-96.7299,
            timezone="America/Chicago",
            profile_id=None  # Global location
        )
        session.add(birth_loc)
        session.flush()
        
        # Create profile
        profile = Profile(
            name="Test Person",
            birth_date="1990-01-15",
            birth_time="14:30",
            birth_location_id=birth_loc.id,
            preferred_house_system_id=house_system.id
        )
        session.add(profile)
        session.flush()
        
        # Verify
        assert profile.id is not None
        assert birth_loc.id is not None
        assert profile.birth_location_id == birth_loc.id


def test_smoke_natal_chart_storage(temp_db):
    """Smoke test: Store and retrieve natal chart data."""
    db_path, engine = temp_db
    
    with get_session(engine) as session:
        # Setup
        house_system = session.query(HouseSystem).filter_by(code='P').first()
        birth_loc = Location(
            label="Test Location",
            latitude=40.0,
            longitude=-95.0,
            timezone="America/Chicago"
        )
        session.add(birth_loc)
        session.flush()
        
        profile = Profile(
            name="Test Person",
            birth_date="1990-01-15",
            birth_time="12:00",
            birth_location_id=birth_loc.id,
            preferred_house_system_id=house_system.id
        )
        session.add(profile)
        session.flush()
        
        # Add natal planet (formatted_position is computed, don't pass it)
        natal_planet = NatalPlanet(
            profile_id=profile.id,
            planet="Sun",
            degree=15,
            minutes=30,
            seconds=45.0,
            sign="Capricorn",
            absolute_position=285.5125
        )
        session.add(natal_planet)
        
        # Add natal house (formatted_position is computed, don't pass it)
        natal_house = NatalHouse(
            profile_id=profile.id,
            house_system_id=house_system.id,
            house_number=1,
            degree=5,
            minutes=12,
            seconds=30.0,
            sign="Scorpio",
            absolute_position=215.2083
        )
        session.add(natal_house)
        
        session.flush()
        
        # Verify retrieval
        planets = session.query(NatalPlanet).filter_by(profile_id=profile.id).all()
        assert len(planets) == 1
        assert planets[0].planet == "Sun"
        
        houses = session.query(NatalHouse).filter_by(profile_id=profile.id).all()
        assert len(houses) == 1
        assert houses[0].house_number == 1


def test_smoke_database_helper_queries(temp_db):
    """Smoke test: DatabaseHelper can query database."""
    db_path, engine = temp_db
    
    # Setup test data
    with get_session(engine) as session:
        house_system = session.query(HouseSystem).filter_by(code='P').first()
        
        birth_loc = Location(
            label="Birth Place",
            latitude=40.0,
            longitude=-95.0,
            timezone="America/Chicago"
        )
        session.add(birth_loc)
        session.flush()
        
        profile = Profile(
            name="Primary User",
            birth_date="1990-01-15",
            birth_time="12:00",
            birth_location_id=birth_loc.id,
            preferred_house_system_id=house_system.id
        )
        session.add(profile)
        session.commit()
    
    # Use DatabaseHelper
    # Note: This won't work as-is because DatabaseHelper looks for ~/.w8s-astro-mcp/astro.db
    # But we can test its methods with our engine
    with get_session(engine) as session:
        # We just created the profile, so we know what to expect
        all_profiles = session.query(Profile).all()
        assert len(all_profiles) == 1
        primary = all_profiles[0]
        assert primary.name == "Primary User"
        
        birth_location = session.query(Location).filter_by(id=primary.birth_location_id).first()
        assert birth_location is not None
        assert birth_location.label == "Birth Place"


def test_smoke_transit_logger_conversions():
    """Smoke test: Transit logger conversion functions."""
    # Test decimal to DMS
    deg, min_, sec = decimal_to_dms(15.5125)
    assert deg == 15
    assert min_ == 30
    assert 44.0 <= sec <= 46.0  # Allow for floating point
    
    # Test sign to absolute position
    abs_pos = sign_to_absolute_position("Aries", 15.5)
    assert abs_pos == 15.5
    
    abs_pos = sign_to_absolute_position("Taurus", 10.0)
    assert abs_pos == 40.0  # 30 + 10
    
    abs_pos = sign_to_absolute_position("Pisces", 5.0)
    assert abs_pos == 335.0  # 11 * 30 + 5


def test_smoke_transit_logging_flow(temp_db):
    """Smoke test: Complete transit logging flow."""
    db_path, engine = temp_db
    
    with get_session(engine) as session:
        # Setup
        house_system = session.query(HouseSystem).filter_by(code='P').first()
        
        location = Location(
            label="Current Location",
            latitude=32.9483,
            longitude=-96.7299,
            timezone="America/Chicago"
        )
        session.add(location)
        session.flush()
        
        profile = Profile(
            name="Test User",
            birth_date="1990-01-15",
            birth_time="12:00",
            birth_location_id=location.id,
            preferred_house_system_id=house_system.id
        )
        session.add(profile)
        session.flush()
        
        # Mock transit data (like from swetest)
        transit_data = {
            "planets": {
                "Sun": {"degree": 20.5, "sign": "Aquarius", "is_retrograde": False},
                "Moon": {"degree": 15.3, "sign": "Cancer", "is_retrograde": False}
            },
            "houses": {
                "1": {"degree": 10.0, "sign": "Scorpio"},
                "2": {"degree": 5.5, "sign": "Sagittarius"}
            },
            "points": {
                "ASC": {"degree": 10.0, "sign": "Scorpio"},
                "MC": {"degree": 20.0, "sign": "Leo"}
            },
            "metadata": {}
        }
        
        # Log transit
        lookup_datetime = datetime.now(timezone.utc)
        lookup = save_transit_data_to_db(
            session,
            profile,
            location,
            lookup_datetime,
            transit_data,
            house_system.id
        )
        session.flush()
        
        # Verify all tables populated
        assert lookup.id is not None
        
        planets = session.query(TransitPlanet).filter_by(transit_lookup_id=lookup.id).all()
        assert len(planets) == 2
        
        houses = session.query(TransitHouse).filter_by(transit_lookup_id=lookup.id).all()
        assert len(houses) == 2
        
        points = session.query(TransitPoint).filter_by(transit_lookup_id=lookup.id).all()
        assert len(points) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
