"""Swiss Ephemeris (swetest) integration."""

import subprocess
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .parsers.swetest import parse_swetest_output, SweetestParseError
from .config import Config


class SweetestError(Exception):
    """Raised when swetest command fails."""
    pass


class SweetestIntegration:
    """Handles calling swetest binary and parsing results."""
    
    def __init__(self, config: Config, swetest_path: str = "swetest"):
        """
        Initialize swetest integration.
        
        Args:
            config: Configuration instance
            swetest_path: Path to swetest binary (default: "swetest" in PATH)
        """
        self.config = config
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
    
    def get_current_transits(
        self,
        date_str: Optional[str] = None,
        time_str: str = "12:00",
        location_name: str = "current"
    ) -> Dict[str, Any]:
        """
        Get transits for current location at specified date/time.
        
        Args:
            date_str: Date in YYYY-MM-DD format (default: today)
            time_str: Time in HH:MM format (default: "12:00")
            location_name: Location name from config (default: "current")
        
        Returns:
            Parsed transit data
            
        Raises:
            SweetestError: If location not found or swetest fails
        """
        # Get location
        location = self.config.get_location(location_name)
        if not location:
            raise SweetestError(f"Location '{location_name}' not found in config")
        
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
        
        # Get house system
        house_system = self.config.get_house_system()
        
        # Build swetest command
        # -b: begin date
        # -ut: universal time
        # -p: planets (0-9 = Sun through Pluto)
        # -house: house cusps with long,lat,house_system
        # -fPZS: format - Position, Zodiac, Speed
        # -roundsec: round to seconds
        cmd = [
            self.swetest_path,
            f"-b{swetest_date}",
            f"-ut{time_str}",
            "-p0123456789",  # All major planets
            f"-house{location['longitude']},{location['latitude']},{house_system}",
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
            
            # Parse output
            return parse_swetest_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise SweetestError("swetest command timed out")
        except SweetestParseError as e:
            raise SweetestError(f"Failed to parse swetest output: {e}")
        except Exception as e:
            raise SweetestError(f"Unexpected error running swetest: {e}")
