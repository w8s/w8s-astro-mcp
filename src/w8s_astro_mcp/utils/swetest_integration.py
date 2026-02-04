"""Integration with Swiss Ephemeris (swetest) binary."""

import subprocess
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
from .parsers.swetest import parse_swetest_output, SweetestParseError


class SweetestError(Exception):
    """Raised when swetest execution fails."""
    pass


class SweetestIntegration:
    """Handles calling swetest binary and parsing results."""
    
    def __init__(self, swetest_path: str = "swetest"):
        """
        Initialize swetest integration.
        
        Args:
            swetest_path: Path to swetest binary (default: "swetest" from PATH)
        """
        self.swetest_path = swetest_path
        self._verify_swetest()
    
    def _verify_swetest(self):
        """Verify that swetest binary is available."""
        try:
            result = subprocess.run(
                [self.swetest_path, "-h"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise SweetestError(f"swetest not working: {result.stderr}")
        except FileNotFoundError:
            raise SweetestError(
                f"swetest binary not found at '{self.swetest_path}'. "
                "Install Swiss Ephemeris or specify correct path."
            )
        except subprocess.TimeoutExpired:
            raise SweetestError("swetest binary timeout")
    
    def get_transits(
        self,
        transit_date: Optional[date] = None,
        transit_time: str = "12:00",
        latitude: float = 0.0,
        longitude: float = 0.0,
        house_system: str = "P"
    ) -> Dict[str, Any]:
        """
        Get transit data for a specific date/time/location.
        
        Args:
            transit_date: Date for transits (default: today)
            transit_time: Time in HH:MM format (default: "12:00")
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            house_system: House system code (P=Placidus, K=Koch, etc.)
        
        Returns:
            Parsed transit data dictionary
            
        Raises:
            SweetestError: If swetest execution fails
            SweetestParseError: If output cannot be parsed
        """
        if transit_date is None:
            transit_date = date.today()
        
        # Format date for swetest (day.month.year)
        date_str = f"{transit_date.day}.{transit_date.month}.{transit_date.year}"
        
        # Build swetest command
        # -b: begin date
        # -ut: universal time
        # -p: planets (0-9 = Sun through Pluto)
        # -house: house cusps with lat,long,house_system
        # -fPZS: format with Position, Zodiac position, Speed
        # -roundsec: round to seconds
        cmd = [
            self.swetest_path,
            f"-b{date_str}",
            f"-ut{transit_time}",
            "-p0123456789",  # All planets
            f"-house{longitude},{latitude},{house_system}",
            "-fPZS",
            "-roundsec"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise SweetestError(f"swetest failed: {result.stderr}")
            
            # Parse the output
            return parse_swetest_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise SweetestError("swetest execution timeout")
        except Exception as e:
            raise SweetestError(f"swetest execution failed: {e}")
    
    def get_transits_for_config(
        self,
        config_data: Dict[str, Any],
        transit_date: Optional[date] = None,
        transit_time: str = "12:00",
        location_name: str = "current"
    ) -> Dict[str, Any]:
        """
        Get transits using configuration data.
        
        Args:
            config_data: Configuration dictionary from Config.data
            transit_date: Date for transits (default: today)
            transit_time: Time in HH:MM format
            location_name: Name of location from config (default: "current")
        
        Returns:
            Parsed transit data dictionary
            
        Raises:
            SweetestError: If config is incomplete or swetest fails
        """
        # Get location
        if location_name == "current":
            current_name = config_data.get("locations", {}).get("current")
            if not current_name:
                raise SweetestError("No current location set in config")
            location_name = current_name
        
        location = config_data.get("locations", {}).get(location_name)
        if not location:
            raise SweetestError(f"Location '{location_name}' not found in config")
        
        # Get house system
        house_system = config_data.get("house_system", "P")
        
        return self.get_transits(
            transit_date=transit_date,
            transit_time=transit_time,
            latitude=location["latitude"],
            longitude=location["longitude"],
            house_system=house_system
        )
