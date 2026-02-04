"""Configuration management for w8s-astro-mcp."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigManager:
    """Manages configuration for astrological calculations."""
    
    # Default config location
    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "w8s-astro-mcp"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
    
    # Default configuration
    DEFAULT_CONFIG = {
        "birth_data": None,
        "locations": {
            "current": None
        },
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
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Optional custom config file path
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_FILE
        self.config = self._load_or_create()
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load existing config or create default."""
        if self.config_path.exists():
            return self._load()
        else:
            # Create directory if needed
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            # Save default config
            self._save(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _load(self) -> Dict[str, Any]:
        """Load config from file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults (in case new keys were added)
                merged = self.DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to load config from {self.config_path}: {e}")
    
    def _save(self, config: Dict[str, Any]) -> None:
        """Save config to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            raise ValueError(f"Failed to save config to {self.config_path}: {e}")
    
    def save(self) -> None:
        """Save current config to file."""
        self._save(self.config)
    
    # Birth data methods
    
    def get_birth_data(self) -> Optional[Dict[str, Any]]:
        """Get birth data if configured."""
        return self.config.get("birth_data")
    
    def set_birth_data(
        self,
        date: str,  # YYYY-MM-DD
        time: str,  # HH:MM or HH:MM:SS
        location_name: str,
        latitude: float,
        longitude: float,
        timezone: str
    ) -> None:
        """
        Set birth data.
        
        Args:
            date: Birth date in YYYY-MM-DD format
            time: Birth time in HH:MM or HH:MM:SS format
            location_name: Name of birth location
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            timezone: IANA timezone (e.g., "America/New_York")
        """
        # Validate date
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Use YYYY-MM-DD")
        
        # Validate time
        try:
            if len(time.split(':')) == 2:
                datetime.strptime(time, "%H:%M")
            else:
                datetime.strptime(time, "%H:%M:%S")
        except ValueError:
            raise ValueError(f"Invalid time format: {time}. Use HH:MM or HH:MM:SS")
        
        # Validate coordinates
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}. Must be between -90 and 90")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}. Must be between -180 and 180")
        
        self.config["birth_data"] = {
            "date": date,
            "time": time,
            "location": {
                "name": location_name,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone
            }
        }
        self.save()
    
    # Location methods
    
    def get_location(self, name: str = "current") -> Optional[Dict[str, Any]]:
        """
        Get a named location or current location.
        
        Args:
            name: Location name or "current"
        
        Returns:
            Location dict or None if not found
        """
        locations = self.config.get("locations", {})
        
        if name == "current":
            # Get current location reference
            current_ref = locations.get("current")
            if current_ref and current_ref in locations:
                return locations[current_ref]
            return None
        
        return locations.get(name)
    
    def set_location(
        self,
        name: str,
        location_name: str,
        latitude: float,
        longitude: float,
        timezone: str
    ) -> None:
        """
        Add or update a named location.
        
        Args:
            name: Internal name for the location (e.g., "home", "work")
            location_name: Display name
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            timezone: IANA timezone
        """
        # Validate coordinates
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")
        
        if "locations" not in self.config:
            self.config["locations"] = {}
        
        self.config["locations"][name] = {
            "name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone
        }
        self.save()
    
    def set_current_location(self, name: str) -> None:
        """
        Set which location is current.
        
        Args:
            name: Name of existing location to set as current
        """
        if name not in self.config.get("locations", {}):
            raise ValueError(f"Location '{name}' not found. Add it first with set_location()")
        
        self.config["locations"]["current"] = name
        self.save()
    
    def list_locations(self) -> Dict[str, Dict[str, Any]]:
        """Get all named locations (excluding 'current' reference)."""
        locations = self.config.get("locations", {}).copy()
        locations.pop("current", None)  # Remove the reference key
        return locations
    
    # House system
    
    def get_house_system(self) -> str:
        """Get house system code (e.g., 'P' for Placidus)."""
        return self.config.get("house_system", "P")
    
    def set_house_system(self, system: str) -> None:
        """
        Set house system.
        
        Args:
            system: House system code (P=Placidus, K=Koch, W=Whole Sign, etc.)
        """
        valid_systems = ["P", "K", "O", "R", "C", "E", "V", "W", "X", "H", "T", "B", "M"]
        if system not in valid_systems:
            raise ValueError(f"Invalid house system: {system}. Valid: {valid_systems}")
        
        self.config["house_system"] = system
        self.save()
    
    # Thresholds
    
    def get_threshold(self, name: str) -> Optional[Any]:
        """Get a specific threshold value."""
        return self.config.get("thresholds", {}).get(name)
    
    def set_threshold(self, name: str, value: Any) -> None:
        """Set a threshold value."""
        if "thresholds" not in self.config:
            self.config["thresholds"] = {}
        
        self.config["thresholds"][name] = value
        self.save()
    
    # Enabled tools
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled."""
        return tool_name in self.config.get("enabled_tools", [])
    
    def enable_tool(self, tool_name: str) -> None:
        """Enable a tool."""
        if "enabled_tools" not in self.config:
            self.config["enabled_tools"] = []
        
        if tool_name not in self.config["enabled_tools"]:
            self.config["enabled_tools"].append(tool_name)
            self.save()
    
    def disable_tool(self, tool_name: str) -> None:
        """Disable a tool."""
        if tool_name in self.config.get("enabled_tools", []):
            self.config["enabled_tools"].remove(tool_name)
            self.save()
    
    # Validation
    
    def is_configured(self) -> bool:
        """Check if basic configuration is complete."""
        return (
            self.get_birth_data() is not None and
            self.get_location("current") is not None
        )
    
    def get_config_status(self) -> Dict[str, Any]:
        """Get configuration status for display."""
        birth_data = self.get_birth_data()
        current_loc = self.get_location("current")
        
        return {
            "configured": self.is_configured(),
            "has_birth_data": birth_data is not None,
            "has_current_location": current_loc is not None,
            "birth_location": birth_data["location"]["name"] if birth_data else None,
            "current_location": current_loc["name"] if current_loc else None,
            "house_system": self.get_house_system(),
            "config_path": str(self.config_path)
        }
