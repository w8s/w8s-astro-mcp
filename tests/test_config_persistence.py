"""Tests for config file persistence and directory creation."""

import pytest
import tempfile
from pathlib import Path
from w8s_astro_mcp.config import Config


def test_config_directory_created():
    """Test that config directory is created when it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent" / "subdir" / "config.json"
        
        # Directory shouldn't exist yet
        assert not config_path.parent.exists()
        
        # Create config
        config = Config(str(config_path))
        
        # Directory should now exist
        assert config_path.parent.exists()
        assert config_path.parent.is_dir()


def test_config_file_persists_after_save():
    """Test that config file actually exists on disk after save()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        
        # Create and save config
        config = Config(str(config_path))
        config.load()
        
        location = {
            "name": "Test",
            "latitude": 40.0,
            "longitude": -74.0,
            "timezone": "UTC"
        }
        config.set_birth_data("1990-05-15", "14:30", location)
        config.save()
        
        # File should exist
        assert config_path.exists()
        assert config_path.is_file()
        
        # File should have content
        assert config_path.stat().st_size > 0


def test_default_config_path_uses_home_directory():
    """Test that default config path is in home directory."""
    config = Config()  # No path specified
    
    # Should be ~/.w8s-astro-mcp/config.json
    assert str(config.config_path).startswith(str(Path.home()))
    assert ".w8s-astro-mcp" in str(config.config_path)
    assert "config.json" in str(config.config_path)


def test_config_survives_multiple_instances():
    """Test that config persists across multiple Config instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        
        # First instance - create and save
        config1 = Config(str(config_path))
        config1.load()
        location = {
            "name": "NYC",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York"
        }
        config1.set_birth_data("1990-05-15", "14:30", location)
        config1.save()
        
        # Second instance - load existing
        config2 = Config(str(config_path))
        config2.load()
        
        # Data should match
        assert config2.is_configured()
        birth_data = config2.get_birth_data()
        assert birth_data["date"] == "1990-05-15"
        assert birth_data["location"]["name"] == "NYC"
