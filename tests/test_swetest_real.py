"""Integration tests that require swetest binary installed.

These tests are SKIPPED if swetest is not available.
Run with: pytest tests/test_swetest_real.py -v

These tests verify the swetest integration works with real swetest binary.
"""

import pytest
import subprocess
import os
from datetime import datetime
from pathlib import Path
import tempfile

from w8s_astro_mcp.utils.swetest_integration import SweetestIntegration, SweetestError
from w8s_astro_mcp.database import initialize_database, get_session
from w8s_astro_mcp.models import Profile, Location, HouseSystem


def get_swetest_path():
    """Get swetest path from environment or default."""
    return os.environ.get("SWETEST_PATH", "swetest")


def swetest_available():
    """Check if swetest binary is available."""
    swetest_path = get_swetest_path()
    try:
        result = subprocess.run(
            [swetest_path, "-h"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip all tests in this file if swetest not available
pytestmark = pytest.mark.skipif(
    not swetest_available(),
    reason="swetest binary not installed"
)


@pytest.fixture
def test_db():
    """Create temporary database with test data."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    # Initialize with schema
    engine = initialize_database(db_path, echo=False)
    
    # Seed data
    with get_session(engine) as session:
        # Add house systems
        house_system = HouseSystem(code='P', name='Placidus', description='Placidus house system')
        session.add(house_system)
        session.flush()
        
        # Add test location (Richardson, TX)
        location = Location(
            label="Richardson, TX",
            latitude=32.9483,
            longitude=-96.7299,
            timezone="America/Chicago"
        )
        session.add(location)
        session.flush()
        
        # Add test profile
        profile = Profile(
            name="Test User",
            birth_date="1981-05-06",
            birth_time="00:50",
            birth_location_id=location.id,
            preferred_house_system_id=house_system.id
        )
        session.add(profile)
        session.commit()
    
    yield db_path, engine, location
    
    # Cleanup
    if db_path.exists():
        os.remove(db_path)


class TestRealSweetest:
    """Integration tests with real swetest binary."""
    
    def test_get_transits_real_call(self, test_db):
        """Test actually calling swetest binary."""
        db_path, engine, location = test_db
        
        swetest_path = get_swetest_path()
        integration = SweetestIntegration(swetest_path=swetest_path)
        
        # Get transits for a known date using direct lat/long
        result = integration.get_transits(
            latitude=location.latitude,
            longitude=location.longitude,
            date_str="2026-02-03",
            time_str="12:00",
            house_system_code="P"
        )
        
        # Verify structure
        assert "planets" in result
        assert "houses" in result
        assert "points" in result
        assert "metadata" in result
        
        # Verify we got all planets
        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        for planet in expected_planets:
            assert planet in result["planets"]
            assert "sign" in result["planets"][planet]
            assert "degree" in result["planets"][planet]
        
        # Verify we got 12 houses (keys are strings: '1'-'12')
        for house_num in range(1, 13):
            assert str(house_num) in result["houses"]
        
        # Verify metadata
        assert result["metadata"]["date"] == "2026-02-03"
        assert result["metadata"]["time"] == "12:00:00"
        assert result["metadata"]["latitude"] == 32.9483
        assert result["metadata"]["longitude"] == -96.7299
        
        print("\n✅ Real swetest call successful!")
        print(f"Sun is at {result['planets']['Sun']['degree']:.2f}° {result['planets']['Sun']['sign']}")
    
    def test_get_transits_today(self, test_db):
        """Test getting today's transits."""
        db_path, engine, location = test_db
        
        integration = SweetestIntegration()
        
        # Get transits for today (date_str=None defaults to today)
        result = integration.get_transits(
            latitude=location.latitude,
            longitude=location.longitude,
            time_str="12:00"
        )
        
        # Should have today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert result["metadata"]["date"] == today
        
        print(f"\n✅ Got transits for today: {today}")
