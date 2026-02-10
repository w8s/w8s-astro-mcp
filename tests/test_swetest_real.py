"""Integration tests that require swetest binary installed.

These tests are SKIPPED if swetest is not available.
Run with: pytest tests/test_swetest_real.py -v
"""

import pytest
import subprocess
import os
from datetime import datetime

from w8s_astro_mcp.utils.swetest_integration import SweetestIntegration, SweetestError
from w8s_astro_mcp.config import Config


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
def real_config(tmp_path):
    """Create config with real location."""
    config_file = tmp_path / "config.json"
    config = Config(str(config_file))
    config.load()
    
    # Richardson, TX
    config.set_location(
        "home",
        32.9483,
        -96.7297,
        "America/Chicago",
        "Richardson, TX"
    )
    config.set_current_location("home")
    
    return config


class TestRealSweetest:
    """Integration tests with real swetest binary."""
    
    def test_get_transits_real_call(self, real_config):
        """Test actually calling swetest binary."""
        swetest_path = get_swetest_path()
        integration = SweetestIntegration(real_config, swetest_path=swetest_path)
        
        # Get transits for a known date
        result = integration.get_current_transits(
            date_str="2026-02-03",
            time_str="12:00"
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
        
        # Verify we got 12 houses
        for house_num in range(1, 13):
            assert house_num in result["houses"]
        
        # Verify metadata
        assert result["metadata"]["date"] == "2026-02-03"
        assert result["metadata"]["time"] == "12:00:00"
        assert result["metadata"]["latitude"] == 32.9483
        assert result["metadata"]["longitude"] == -96.7297
        
        print("\n✅ Real swetest call successful!")
        print(f"Sun is at {result['planets']['Sun']['degree']:.2f}° {result['planets']['Sun']['sign']}")
    
    def test_get_transits_today(self, real_config):
        """Test getting today's transits."""
        integration = SweetestIntegration(real_config)
        
        result = integration.get_current_transits()
        
        # Should have today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert result["metadata"]["date"] == today
        
        print(f"\n✅ Got transits for today: {today}")
