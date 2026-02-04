"""Configuration management for w8s-astro-mcp."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


class Config:
    """Manages astrological configuration including birth data and locations."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Default: ~/.w8s-astro-mcp/config.json
            self.config_path = Path.home() / ".w8s-astro-mcp" / "config.json"
        
        self.data: Dict[str, Any] = {}
        self._ensure_config_dir()
    
    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from disk.
        
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigError: If config file is malformed
        """
        if not self.config_path.exists():
            # Return default empty config
            self.data = self._get_default_config()
            return self.data
        
        try:
            with open(self.config_path, 'r') as f:
                self.data = json.load(f)
            return self.data
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigError(f"Could not load config: {e}")
    
    def save(self):
        """
        Save configuration to disk.
        
        Raises:
            ConfigError: If config cannot be saved
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            raise ConfigError(f"Could not save config: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure."""
        return {
            "birth_data": None,
            "locations": {},
            "house_system": "P",  # Placidus
            "enabled_tools": [
                "setup_astro_config",
                "get_daily_transits",
                "get_transit_markdown",
                "check_major_shifts"
            ],
            "thresholds": {
                "anaretic_degree_min": 28,
                "early_degree_max": 1,
                "sign_change_warning_days": 2,
                "stellium_min_planets": 3
            }
        }
    
    def is_configured(self) -> bool:
        """Check if basic configuration (birth data) is set."""
        return self.data.get("birth_data") is not None
    
    def get_birth_data(self) -> Optional[Dict[str, Any]]:
        """Get birth data configuration."""
        return self.data.get("birth_data")
    
    def set_birth_data(self, date: str, time: str, location: Dict[str, Any]):
        """
        Set birth data.
        
        Args:
            date: Birth date in YYYY-MM-DD format
            time: Birth time in HH:MM format (24-hour)
            location: Dict with 'name', 'latitude', 'longitude', 'timezone'
        
        Raises:
            ConfigError: If data is invalid
        """
        # Validate date
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ConfigError(f"Invalid date format: {date}. Use YYYY-MM-DD")
        
        # Validate time
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            raise ConfigError(f"Invalid time format: {time}. Use HH:MM (24-hour)")
        
        # Validate location
        required_fields = ['name', 'latitude', 'longitude', 'timezone']
        for field in required_fields:
            if field not in location:
                raise ConfigError(f"Location missing required field: {field}")
        
        self.data["birth_data"] = {
            "date": date,
            "time": time,
            "location": location
        }
    
    def get_location(self, name: str = "current") -> Optional[Dict[str, Any]]:
        """
        Get a named location.
        
        Args:
            name: Location name or "current" for current location
            
        Returns:
            Location dict or None if not found
        """
        if name == "current":
            current_name = self.data.get("locations", {}).get("current")
            if not current_name:
                return None
            name = current_name
        
        return self.data.get("locations", {}).get(name)
    
    def set_location(self, name: str, latitude: float, longitude: float, 
                     timezone: str, display_name: Optional[str] = None):
        """
        Set a named location.
        
        Args:
            name: Location identifier (e.g., "home", "work")
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            timezone: Timezone string (e.g., "America/Chicago")
            display_name: Optional human-readable name
        """
        if "locations" not in self.data:
            self.data["locations"] = {}
        
        self.data["locations"][name] = {
            "name": display_name or name,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone
        }
    
    def set_current_location(self, name: str):
        """
        Set which location is "current".
        
        Args:
            name: Name of location to set as current
            
        Raises:
            ConfigError: If location doesn't exist
        """
        if name not in self.data.get("locations", {}):
            raise ConfigError(f"Location '{name}' not found")
        
        if "locations" not in self.data:
            self.data["locations"] = {}
        
        self.data["locations"]["current"] = name
    
    def get_house_system(self) -> str:
        """Get house system code (default: P for Placidus)."""
        return self.data.get("house_system", "P")
    
    def set_house_system(self, system: str):
        """
        Set house system.
        
        Args:
            system: House system code (P=Placidus, K=Koch, etc.)
        """
        self.data["house_system"] = system
    
    def get_thresholds(self) -> Dict[str, int]:
        """Get thresholds for detecting major shifts."""
        return self.data.get("thresholds", self._get_default_config()["thresholds"])
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled."""
        enabled = self.data.get("enabled_tools", [])
        return tool_name in enabled
