"""Unit tests for configuration management."""

import pytest
import json
import tempfile
from pathlib import Path
from w8s_astro_mcp.config import Config, ConfigError


class TestConfig:
    """Test configuration management."""
    
    def test_default_config(self, tmp_path):
        """Test that default config is created."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        assert config.data is not None
        assert "birth_data" in config.data
        assert "locations" in config.data
        assert "house_system" in config.data
        assert config.data["house_system"] == "P"
    
    def test_is_configured_false_by_default(self, tmp_path):
        """Test that config starts unconfigured."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        assert config.is_configured() is False
    
    def test_set_birth_data(self, tmp_path):
        """Test setting birth data."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        location = {
            "name": "New York, NY",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York"
        }
        
        config.set_birth_data("1990-05-15", "14:30", location)
        
        assert config.is_configured() is True
        birth_data = config.get_birth_data()
        assert birth_data["date"] == "1990-05-15"
        assert birth_data["time"] == "14:30"
        assert birth_data["location"]["name"] == "New York, NY"
    
    def test_invalid_date_format(self, tmp_path):
        """Test that invalid date format raises error."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        location = {
            "name": "Test",
            "latitude": 0.0,
            "longitude": 0.0,
            "timezone": "UTC"
        }
        
        with pytest.raises(ConfigError, match="Invalid date format"):
            config.set_birth_data("05/15/1990", "14:30", location)
    
    def test_invalid_time_format(self, tmp_path):
        """Test that invalid time format raises error."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        location = {
            "name": "Test",
            "latitude": 0.0,
            "longitude": 0.0,
            "timezone": "UTC"
        }
        
        with pytest.raises(ConfigError, match="Invalid time format"):
            config.set_birth_data("1990-05-15", "2:30 PM", location)
    
    def test_missing_location_field(self, tmp_path):
        """Test that missing location fields raise error."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        # Missing timezone
        location = {
            "name": "Test",
            "latitude": 0.0,
            "longitude": 0.0
        }
        
        with pytest.raises(ConfigError, match="missing required field"):
            config.set_birth_data("1990-05-15", "14:30", location)
    
    def test_save_and_load(self, tmp_path):
        """Test saving and loading config."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        location = {
            "name": "Test Location",
            "latitude": 40.0,
            "longitude": -74.0,
            "timezone": "America/New_York"
        }
        
        config.set_birth_data("1990-05-15", "14:30", location)
        config.save()
        
        # Load in new instance
        config2 = Config(str(config_file))
        config2.load()
        
        assert config2.is_configured() is True
        birth_data = config2.get_birth_data()
        assert birth_data["date"] == "1990-05-15"
    
    def test_set_and_get_location(self, tmp_path):
        """Test setting and getting named locations."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        config.set_location("home", 32.9483, -96.7297, "America/Chicago", "Richardson, TX")
        
        loc = config.get_location("home")
        assert loc is not None
        assert loc["name"] == "Richardson, TX"
        assert loc["latitude"] == 32.9483
        assert loc["longitude"] == -96.7297
    
    def test_current_location(self, tmp_path):
        """Test setting and getting current location."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        config.set_location("home", 32.9483, -96.7297, "America/Chicago")
        config.set_location("work", 32.7767, -96.7970, "America/Chicago")
        config.set_current_location("home")
        
        current = config.get_location("current")
        assert current is not None
        assert current["latitude"] == 32.9483
        
        # Change current
        config.set_current_location("work")
        current = config.get_location("current")
        assert current["latitude"] == 32.7767
    
    def test_set_current_location_not_found(self, tmp_path):
        """Test that setting nonexistent current location raises error."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        with pytest.raises(ConfigError, match="not found"):
            config.set_current_location("nonexistent")
    
    def test_house_system(self, tmp_path):
        """Test getting and setting house system."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        # Default is Placidus
        assert config.get_house_system() == "P"
        
        # Change to Koch
        config.set_house_system("K")
        assert config.get_house_system() == "K"
    
    def test_thresholds(self, tmp_path):
        """Test getting thresholds."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        thresholds = config.get_thresholds()
        assert "anaretic_degree_min" in thresholds
        assert thresholds["anaretic_degree_min"] == 28
        assert thresholds["stellium_min_planets"] == 3
    
    def test_tool_enabled(self, tmp_path):
        """Test checking if tools are enabled."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        assert config.is_tool_enabled("get_daily_transits") is True
        assert config.is_tool_enabled("nonexistent_tool") is False
