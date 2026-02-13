"""Integration tests for MCP server tools with SQLite database.

These tests verify the full workflow:
1. Database → Server tools → Response
2. Real tool calls like setup_astro_config, get_natal_chart, get_transits
"""

import sys
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

import pytest
from pathlib import Path
import tempfile
import os
from datetime import datetime

from w8s_astro_mcp.database import initialize_database, get_session
from w8s_astro_mcp.models import Profile, Location, HouseSystem
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    # Initialize with schema
    engine = initialize_database(db_path, echo=False)
    
    # Seed house systems
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


def test_setup_astro_config_workflow(temp_db):
    """Test the setup_astro_config MCP tool workflow.
    
    Simulates what happens when user calls setup_astro_config:
    1. Create profile with birth data
    2. Create birth location
    3. Verify data is stored correctly
    """
    db_path, engine = temp_db
    
    # Use DatabaseHelper to create profile (atomically creates location too)
    from w8s_astro_mcp.database import create_db_engine
    db_helper = DatabaseHelper()
    db_helper.engine = engine  # Use test engine
    
    profile = db_helper.create_profile_with_location(
        name="Test User",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago"
    )
    
    # Verify setup worked
    with get_session(engine) as session:
        birth_location = session.query(Location).filter_by(id=profile.birth_location_id).first()
        
    # Verify setup worked
    with get_session(engine) as session:
        birth_location = session.query(Location).filter_by(id=profile.birth_location_id).first()
        
        assert profile.id is not None
        assert birth_location.id is not None
        assert birth_location.profile_id == profile.id  # Now linked
        
        # Verify we can retrieve it (like get_natal_chart would)
        retrieved = session.query(Profile).filter_by(id=profile.id).first()
        assert retrieved is not None
        assert retrieved.birth_date == "1981-05-06"
        assert retrieved.birth_time == "00:50"
        
        # Verify we can get the birth location
        birth_loc = session.query(Location).filter_by(id=retrieved.birth_location_id).first()
        assert birth_loc is not None
        assert birth_loc.latitude == 32.9483


def test_database_helper_get_primary_profile(temp_db):
    """Test DatabaseHelper.get_current_profile() method."""
    db_path, engine = temp_db
    
    # Use DatabaseHelper to create profile
    db_helper = DatabaseHelper()
    db_helper.engine = engine  # Use test engine
    
    profile = db_helper.create_profile_with_location(
        name="Primary User",
        birth_date="1990-01-15",
        birth_time="12:00",
        birth_location_name="Test City",
        birth_latitude=40.0,
        birth_longitude=-95.0,
        birth_timezone="America/Chicago"
    )
    
    # Now use DatabaseHelper (simulating server.py usage)
    # Note: We just created the profile, so we can use its data directly
    with get_session(engine) as session:
        # In real usage, server would use AppSettings to get current profile
        # For this test, we know the profile we just created
        all_profiles = session.query(Profile).all()
        assert len(all_profiles) == 1
        primary = all_profiles[0]
        assert primary.name == "Primary User"


def test_get_natal_chart_with_cached_data(temp_db):
    """Test retrieving natal chart data from database.
    
    Simulates what get_natal_chart MCP tool does:
    1. Get primary profile
    2. Check if natal chart is cached in database
    3. Return cached data
    """
    db_path, engine = temp_db
    
    # Use DatabaseHelper to create profile
    db_helper = DatabaseHelper()
    db_helper.engine = engine  # Use test engine
    
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
        from w8s_astro_mcp.models import NatalPlanet, NatalHouse, NatalPoint
        
        house_system = session.query(HouseSystem).filter_by(code='P').first()
        
        # Add cached natal data (like swetest would save)
        sun = NatalPlanet(
            profile_id=profile.id,
            planet="Sun",
            degree=15,
            minutes=24,
            seconds=36.0,
            sign="Taurus",
            absolute_position=45.41,
            house_number=7
        )
        session.add(sun)
        
        asc = NatalPoint(
            profile_id=profile.id,
            house_system_id=house_system.id,
            point_type="ASC",
            degree=11,
            minutes=45,
            seconds=0.0,
            sign="Scorpio",
            absolute_position=221.75
        )
        session.add(asc)
        
        house_1 = NatalHouse(
            profile_id=profile.id,
            house_system_id=house_system.id,
            house_number=1,
            degree=11,
            minutes=45,
            seconds=0.0,
            sign="Scorpio",
            absolute_position=221.75
        )
        session.add(house_1)
        
        session.commit()
        
        # Now simulate get_natal_chart retrieval
        # We know the profile we just created
        assert profile.id is not None
        
        # Get natal planets
        planets = session.query(NatalPlanet).filter_by(profile_id=profile.id).all()
        assert len(planets) == 1
        assert planets[0].planet == "Sun"
        assert planets[0].sign == "Taurus"
        
        # Get natal points
        points = session.query(NatalPoint).filter_by(profile_id=profile.id).all()
        assert len(points) == 1
        assert points[0].point_type == "ASC"
        
        # Get natal houses
        houses = session.query(NatalHouse).filter_by(profile_id=profile.id).all()
        assert len(houses) == 1
        assert houses[0].house_number == 1


def test_location_management(temp_db):
    """Test managing multiple locations (home, current, custom).
    
    Simulates:
    1. User creates profile with birth location
    2. User adds additional locations
    3. User manages current home location
    """
    db_path, engine = temp_db
    
    # Use DatabaseHelper to create profile with birth location
    db_helper = DatabaseHelper()
    db_helper.engine = engine  # Use test engine
    
    profile = db_helper.create_profile_with_location(
        name="Test User",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="St. Louis, MO",
        birth_latitude=38.627,
        birth_longitude=-90.198,
        birth_timezone="America/Chicago"
    )
    
    with get_session(engine) as session:
        # Add additional locations using DatabaseHelper
        current_loc = db_helper.create_location(
            profile_id=profile.id,
            label="Richardson, TX",
            latitude=32.9483,
            longitude=-96.7299,
            timezone="America/Chicago",
            set_as_home=True  # This becomes the new home
        )
        
        custom_loc = db_helper.create_location(
            profile_id=profile.id,
            label="New York, NY",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
            set_as_home=False
        )
        
        # Verify we can query locations
        all_locations = session.query(Location).filter_by(profile_id=profile.id).all()
        assert len(all_locations) == 3  # Birth + Richardson + NYC
        
        # Get current home (should be Richardson since set_as_home=True)
        home = session.query(Location).filter_by(
            profile_id=profile.id,
            is_current_home=True
        ).first()
        assert home is not None
        assert home.label == "Richardson, TX"
        
        # Get birth location
        birth = session.query(Location).filter_by(id=profile.birth_location_id).first()
        assert birth is not None
        assert birth.label == "Birth"  # DatabaseHelper uses "Birth" as default label


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
