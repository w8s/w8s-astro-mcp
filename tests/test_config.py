"""Unit tests for configuration manager."""

import pytest
import tempfile
import json
from pathlib import Path
from w8s_astro_mcp.config import ConfigManager


@pytest.fixture
def temp_config_path(tmp_path):
    """Create a temporary config file path."""
    return tmp_path / "test_config.json"


@pytest.fixture(scope="function")  # Ensure fresh instance per test
def config_manager(tmp_path):
    """Create a config manager with temporary path."""
    # Use tmp_path directly so each test gets a new path
    config_path = tmp_path / f"config_{id(tmp_path)}.json"
    return ConfigManager(config_path=config_path)


class TestConfigManager:
    """Test configuration management."""
    
    def test_creates_default_config(self, temp_config_path):
        """Test that default config is created if none exists."""
        manager = ConfigManager(config_path=temp_config_path)
        
        assert temp_config_path.exists()
        assert manager.config["house_system"] == "P"
        assert "thresholds" in manager.config
    
    def test_loads_existing_config(self, temp_config_path):
        """Test loading existing configuration."""
        # Create a config file
        test_config = {
            "birth_data": {"date": "2000-01-01"},
            "house_system": "K"
        }
        with open(temp_config_path, 'w') as f:
            json.dump(test_config, f)
        
        manager = ConfigManager(config_path=temp_config_path)
        assert manager.config["house_system"] == "K"
        assert manager.config["birth_data"]["date"] == "2000-01-01"
    
    def test_set_birth_data(self, config_manager):
        """Test setting birth data."""
        config_manager.set_birth_data(
            date="1990-05-15",
            time="14:30",
            location_name="New York, NY",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
        
        birth_data = config_manager.get_birth_data()
        assert birth_data["date"] == "1990-05-15"
        assert birth_data["time"] == "14:30"
        assert birth_data["location"]["name"] == "New York, NY"
        assert birth_data["location"]["latitude"] == 40.7128
    
    def test_invalid_date_format(self, config_manager):
        """Test that invalid date format raises error."""
        with pytest.raises(ValueError, match="Invalid date format"):
            config_manager.set_birth_data(
                date="05/15/1990",  # Wrong format
                time="14:30",
                location_name="NYC",
                latitude=40.7128,
                longitude=-74.0060,
                timezone="America/New_York"
            )
    
    def test_invalid_coordinates(self, config_manager):
        """Test that invalid coordinates raise errors."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            config_manager.set_birth_data(
                date="1990-05-15",
                time="14:30",
                location_name="Invalid",
                latitude=100,  # Out of range
                longitude=-74.0060,
                timezone="America/New_York"
            )
    
    def test_set_and_get_location(self, config_manager):
        """Test setting and getting locations."""
        config_manager.set_location(
            name="home",
            location_name="Richardson, TX",
            latitude=32.9483,
            longitude=-96.7297,
            timezone="America/Chicago"
        )
        
        location = config_manager.get_location("home")
        assert location["name"] == "Richardson, TX"
        assert location["latitude"] == 32.9483
    
    def test_set_current_location(self, config_manager):
        """Test setting current location."""
        # First add a location
        config_manager.set_location(
            "home", "Home", 40.7, -74.0, "America/New_York"
        )
        
        # Set it as current
        config_manager.set_current_location("home")
        
        # Get current location
        current = config_manager.get_location("current")
        assert current["name"] == "Home"
    
    def test_current_location_must_exist(self, config_manager):
        """Test that setting non-existent location as current fails."""
        with pytest.raises(ValueError, match="not found"):
            config_manager.set_current_location("nonexistent")
    
    def test_list_locations(self, config_manager):
        """Test listing locations excludes 'current' reference."""
        config_manager.set_location("home", "Home", 40.7, -74.0, "America/New_York")
        config_manager.set_location("work", "Work", 40.8, -73.9, "America/New_York")
        config_manager.set_current_location("home")
        
        locations = config_manager.list_locations()
        assert "home" in locations
        assert "work" in locations
        assert "current" not in locations  # Should be excluded
    
    def test_house_system(self, config_manager):
        """Test setting house system."""
        assert config_manager.get_house_system() == "P"  # Default
        
        config_manager.set_house_system("K")
        assert config_manager.get_house_system() == "K"
    
    def test_invalid_house_system(self, config_manager):
        """Test that invalid house system raises error."""
        with pytest.raises(ValueError, match="Invalid house system"):
            config_manager.set_house_system("Z")
    
    def test_thresholds(self, config_manager):
        """Test getting and setting thresholds."""
        assert config_manager.get_threshold("anaretic_degree_min") == 28
        
        config_manager.set_threshold("anaretic_degree_min", 29)
        assert config_manager.get_threshold("anaretic_degree_min") == 29
    
    def test_tool_enablement(self, config_manager):
        """Test enabling and disabling tools."""
        assert config_manager.is_tool_enabled("get_daily_transits")
        
        config_manager.disable_tool("get_daily_transits")
        assert not config_manager.is_tool_enabled("get_daily_transits")
        
        config_manager.enable_tool("get_daily_transits")
        assert config_manager.is_tool_enabled("get_daily_transits")
    
    def test_is_configured(self, config_manager):
        """Test configuration status check."""
        assert not config_manager.is_configured()
        
        # Add birth data
        config_manager.set_birth_data(
            "1990-05-15", "14:30", "NYC", 40.7, -74.0, "America/New_York"
        )
        assert not config_manager.is_configured()  # Still need current location
        
        # Add current location
        config_manager.set_location("home", "Home", 40.7, -74.0, "America/New_York")
        config_manager.set_current_location("home")
        assert config_manager.is_configured()
    
    def test_get_config_status(self, config_manager):
        """Test getting configuration status dict."""
        status = config_manager.get_config_status()
        
        assert not status["configured"]
        assert not status["has_birth_data"]
        assert not status["has_current_location"]
        assert status["house_system"] == "P"
    
    def test_persistence(self, temp_config_path):
        """Test that changes persist across instances."""
        # Create first instance and set data
        manager1 = ConfigManager(config_path=temp_config_path)
        manager1.set_birth_data(
            "1990-05-15", "14:30", "NYC", 40.7, -74.0, "America/New_York"
        )
        
        # Create second instance and verify data persisted
        manager2 = ConfigManager(config_path=temp_config_path)
        birth_data = manager2.get_birth_data()
        assert birth_data["date"] == "1990-05-15"
