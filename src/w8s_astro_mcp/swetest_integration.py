"""Swiss Ephemeris (swetest) integration."""

import subprocess
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .parsers.swetest import parse_swetest_output, SweetestParseError


class SweetestError(Exception):
    """Raised when swetest command fails."""
    pass


class SweetestIntegration:
    """Handles calling swetest binary and parsing results."""
    
    def __init__(self, swetest_path: str = "swetest"):
        """
        Initialize swetest integration.
        
        Args:
            swetest_path: Path to swetest binary (default: "swetest" in PATH)
        """
        self.swetest_path = swetest_path
        self._verify_swetest()
    
    def _verify_swetest(self):
        """
        Verify swetest is available.
        
        Raises:
            SweetestError: If swetest is not found or not executable
        """
        try:
            result = subprocess.run(
                [self.swetest_path, "-h"],
                capture_output=True,
                text=True,
                timeout=5
            )
        except FileNotFoundError:
            raise SweetestError(
                f"swetest binary not found at '{self.swetest_path}'. "
                "Install Swiss Ephemeris or specify correct path."
            )
        except subprocess.TimeoutExpired:
            raise SweetestError("swetest binary timed out during verification")
    
    def get_transits(
        self,
        latitude: float,
        longitude: float,
        date_str: Optional[str] = None,
        time_str: str = "12:00",
        house_system_code: str = "P"
    ) -> Dict[str, Any]:
        """
        Get transits for a specific location at specified date/time.
        
        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            date_str: Date in YYYY-MM-DD format (default: today)
            time_str: Time in HH:MM format (default: "12:00")
            house_system_code: House system code (default: "P" for Placidus)
        
        Returns:
            Parsed transit data with 'planets', 'houses', 'points', 'metadata' keys
            
        Raises:
            SweetestError: If swetest fails or output cannot be parsed
        """
        # Use today if no date specified
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Parse date
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise SweetestError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
        
        # Convert to swetest format (day.month.year)
        swetest_date = f"{dt.day}.{dt.month}.{dt.year}"
        
        # Build swetest command
        # -b: begin date
        # -ut: universal time
        # -p: planets (0-9 = Sun through Pluto)
        # -house: house cusps with long,lat,house_system
        # -fPZS: format - Position, Zodiac, Speed
        # Note: Removed -roundsec to avoid split seconds parsing issues
        cmd = [
            self.swetest_path,
            f"-b{swetest_date}",
            f"-ut{time_str}",
            "-p0123456789",  # All major planets
            f"-house{longitude},{latitude},{house_system_code}",
            "-fPZS"
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
            
            # Parse output
            return parse_swetest_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise SweetestError("swetest command timed out")
        except SweetestParseError as e:
            raise SweetestError(f"Failed to parse swetest output: {e}")
        except Exception as e:
            raise SweetestError(f"Unexpected error running swetest: {e}")
    
    # Backwards compatibility wrapper
    def get_current_transits(
        self,
        date_str: Optional[str] = None,
        time_str: str = "12:00",
        location_name: str = "current"
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Backwards compatibility wrapper for old Config-based code.
        
        This method exists to support legacy code that uses Config.
        New code should use get_transits() directly.
        
        Raises:
            NotImplementedError: This method requires refactoring to use new approach
        """
        raise NotImplementedError(
            "get_current_transits() is deprecated. "
            "Use get_transits(latitude, longitude, ...) instead. "
            "See docs/SERVER_REFACTOR_TODO.md for migration guide."
        )
