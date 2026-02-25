"""Test NatalPoint model specifically.

NatalPoint stores special astrological points (ASC, MC, Nodes, etc.)
Similar structure to NatalPlanet/NatalHouse but with point_type field.
"""

import sys
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

import pytest
from pathlib import Path
import tempfile
import os

from w8s_astro_mcp.database import initialize_database, get_session
from w8s_astro_mcp.models import Profile, Location, HouseSystem, NatalPoint


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    # Initialize with schema + seed data (house systems are seeded automatically)
    engine = initialize_database(db_path, echo=False)

    yield db_path, engine
    
    # Cleanup
    if db_path.exists():
        os.remove(db_path)


def test_natal_point_creation(temp_db):
    """Test creating NatalPoint records (ASC, MC)."""
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
        
        # Add ASC (formatted_position is computed, don't pass it)
        asc = NatalPoint(
            profile_id=profile.id,
            house_system_id=house_system.id,
            point_type="ASC",
            degree=10,
            minutes=25,
            seconds=30.5,
            sign="Scorpio",
            absolute_position=220.425
        )
        session.add(asc)
        
        # Add MC (formatted_position is computed, don't pass it)
        mc = NatalPoint(
            profile_id=profile.id,
            house_system_id=house_system.id,
            point_type="MC",
            degree=15,
            minutes=30,
            seconds=45.0,
            sign="Leo",
            absolute_position=135.5125
        )
        session.add(mc)
        
        session.flush()
        
        # Verify retrieval
        points = session.query(NatalPoint).filter_by(profile_id=profile.id).all()
        assert len(points) == 2
        
        # Check ASC
        asc_point = session.query(NatalPoint).filter_by(
            profile_id=profile.id,
            point_type="ASC"
        ).first()
        assert asc_point is not None
        assert asc_point.degree == 10
        assert asc_point.sign == "Scorpio"
        assert asc_point.formatted_position == "10°25'30\" Scorpio"
        
        # Check MC
        mc_point = session.query(NatalPoint).filter_by(
            profile_id=profile.id,
            point_type="MC"
        ).first()
        assert mc_point is not None
        assert mc_point.degree == 15
        assert mc_point.sign == "Leo"
        assert mc_point.formatted_position == "15°30'45\" Leo"


def test_natal_point_to_dict(temp_db):
    """Test NatalPoint.to_dict() method."""
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
        
        # Add ASC
        asc = NatalPoint(
            profile_id=profile.id,
            house_system_id=house_system.id,
            point_type="ASC",
            degree=10,
            minutes=25,
            seconds=30.5,
            sign="Scorpio",
            absolute_position=220.425
        )
        session.add(asc)
        session.flush()
        
        # Convert to dict
        asc_dict = asc.to_dict()
        
        # Verify dict structure
        assert asc_dict["profile_id"] == profile.id
        assert asc_dict["house_system_id"] == house_system.id
        assert asc_dict["point_type"] == "ASC"
        assert asc_dict["degree"] == 10
        assert asc_dict["minutes"] == 25
        assert asc_dict["seconds"] == 30.5
        assert asc_dict["sign"] == "Scorpio"
        assert asc_dict["absolute_position"] == 220.425
        assert "calculated_at" in asc_dict
        assert asc_dict["calculation_method"] == "pysweph"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
