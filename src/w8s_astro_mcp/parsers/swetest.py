"""Parser for Swiss Ephemeris (swetest) output."""

import re
from datetime import datetime
from typing import Dict, Any, Optional


class SweetestParseError(Exception):
    """Raised when swetest output cannot be parsed."""
    pass


# Zodiac sign mappings
SIGNS = {
    "ar": "Aries", "ta": "Taurus", "ge": "Gemini",
    "cn": "Cancer", "le": "Leo", "vi": "Virgo",
    "li": "Libra", "sc": "Scorpio", "sa": "Sagittarius",
    "cp": "Capricorn", "aq": "Aquarius", "pi": "Pisces"
}

# Planet mappings
PLANETS = {
    "Sun": "Sun",
    "Moon": "Moon",
    "Mercury": "Mercury",
    "Venus": "Venus",
    "Mars": "Mars",
    "Jupiter": "Jupiter",
    "Saturn": "Saturn",
    "Uranus": "Uranus",
    "Neptune": "Neptune",
    "Pluto": "Pluto"
}


def parse_degree(degree_str: str) -> Dict[str, Any]:
    """
    Parse a degree string like "14 aq 39'38\"" or "18 aq 42'50.9419" into components.
    
    Handles both formats:
    - Quoted seconds: "14 aq 39'38""
    - Decimal seconds: "18 aq 42'50.9419"
    
    Returns:
        dict with 'degree' (float), 'sign' (str), 'formatted' (str)
        Returns None if format is invalid or sign is not recognized
    """
    # Try decimal format first: "18 aq 42'50.9419" or "18 aq 42' 50.9419" (with space)
    match = re.match(r"(\d+)\s+([a-z]{2})\s+(\d+)'\s*([\d.]+)", degree_str.strip())
    if match:
        degrees, sign_abbr, minutes, seconds = match.groups()
        
        # Validate sign abbreviation
        sign = SIGNS.get(sign_abbr.lower())
        if not sign:
            return None
        
        # Convert to decimal degrees (0-30 within sign)
        decimal_degree = int(degrees) + int(minutes) / 60 + float(seconds) / 3600
        
        return {
            "degree": decimal_degree,
            "sign": sign,
            "formatted": f"{degrees}°{minutes}'{seconds}\""
        }
    
    # Try quoted format: "14 aq 39'38""
    match = re.match(r"(\d+)\s+([a-z]{2})\s+(\d+)'\s*(\d+)\"", degree_str.strip())
    if match:
        degrees, sign_abbr, minutes, seconds = match.groups()
        
        # Validate sign abbreviation
        sign = SIGNS.get(sign_abbr.lower())
        if not sign:
            return None
        
        # Convert to decimal degrees (0-30 within sign)
        decimal_degree = int(degrees) + int(minutes) / 60 + int(seconds) / 3600
        
        return {
            "degree": decimal_degree,
            "sign": sign,
            "formatted": f"{degrees}°{minutes}'{seconds}\""
        }
    
    return None


def parse_swetest_output(output: str) -> Dict[str, Any]:
    """
    Parse swetest output into structured data.
    
    Args:
        output: Raw output from swetest command
    
    Returns:
        Dictionary with parsed transit data
        
    Raises:
        SweetestParseError: If output is empty or missing critical data
    """
    if not output or not output.strip():
        raise SweetestParseError("swetest output is empty")
    
    result = {
        "planets": {},
        "houses": {},
        "points": {},
        "metadata": {}
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Parse date and time
        if line.startswith("date (dmy)"):
            # Example: date (dmy) 3.2.2026 greg.   12:00:00 UT
            match = re.search(r"date \(dmy\)\s+(\d+)\.(\d+)\.(\d+).*?(\d+):(\d+):(\d+)", line)
            if match:
                day, month, year, hour, minute, second = match.groups()
                result["metadata"]["date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                result["metadata"]["time"] = f"{hour}:{minute}:{second}"
        
        # Parse location
        elif line.startswith("geo. long"):
            # Example: geo. long -90.199400, lat 38.627000, alt 0.000000
            match = re.search(r"long\s+([-\d.]+),\s+lat\s+([-\d.]+)", line)
            if match:
                longitude, latitude = match.groups()
                result["metadata"]["longitude"] = float(longitude)
                result["metadata"]["latitude"] = float(latitude)
        
        # Parse house system
        elif "Houses system" in line:
            # Example: Houses system P (Placidus)
            match = re.search(r"Houses system\s+(\w+)\s+\(([^)]+)\)", line)
            if match:
                result["metadata"]["house_system"] = match.group(2)
        
        # Parse planets
        elif any(planet in line for planet in PLANETS.keys()):
            for planet_name in PLANETS.keys():
                if line.startswith(planet_name):
                    # Example: Sun             18 aq 42'50.9419    1° 0'46.3529
                    # Example: Sun             18 aq 42'50.9419    1° 0'46.3529
                    # Example: Mercury         23 aq 54' 3"    1°46'23"
                    # Example: Saturn          29 pi 18' 3.6612    0° 6'16.5684 (note space: 18' and 3.6612 are split)
                    parts = line.split()
                    if len(parts) >= 4:
                        # Check if parts[3] ends with ' and parts[4] starts with digit (split seconds)
                        # e.g., parts[3]="18'" and parts[4]='3.6612' or parts[4]='0"'
                        if len(parts) >= 5 and parts[3].endswith("'") and parts[4][0].isdigit():
                            # Minutes and seconds are split - join them with space
                            position_str = f"{parts[1]} {parts[2]} {parts[3]} {parts[4]}"
                            declination_str = " ".join(parts[5:]) if len(parts) > 5 else ""
                        else:
                            # Normal format - minutes'seconds together
                            position_str = f"{parts[1]} {parts[2]} {parts[3]}"
                            declination_str = " ".join(parts[4:]) if len(parts) > 4 else ""
                        
                        pos_data = parse_degree(position_str)
                        if pos_data:
                            result["planets"][planet_name] = {
                                "sign": pos_data["sign"],
                                "degree": pos_data["degree"],
                                "formatted": pos_data["formatted"],
                                "declination": declination_str.strip()
                            }
                    break
        
        # Parse houses
        elif line.startswith("house "):
            # Example: house  1        24 cp 23'49.2728  392°17'49.4100
            # Example: house  1        23 cp 22' 8"  403°44'50"
            # Example: house  4        17 aq  7' 1.8505  364°37'26.1159  (note extra space before 7)
            #
            # DESIGN DECISION (2026-02-09):
            # House numbers are stored as STRING keys ("1", "2", ..., "12").
            # This is intentional for JSON compatibility and consistency.
            # DO NOT convert to integers.
            match = re.match(r"house\s+(\d+)\s+(.*)", line)
            if match:
                house_num = match.group(1)  # Keep as string - DO NOT convert to int
                rest = match.group(2).strip()
                
                # Position is first 3 space-separated parts: degrees sign minutes'seconds
                # Use split() which handles multiple consecutive spaces
                parts = rest.split()
                if len(parts) >= 3:
                    # Handle potential split seconds like Saturn/Pluto
                    if len(parts) >= 4 and parts[2].endswith("'") and parts[3][0].isdigit():
                        # Minutes and seconds split: "7'" and "1.8505"
                        position_str = f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}"
                    else:
                        # Normal format
                        position_str = f"{parts[0]} {parts[1]} {parts[2]}"
                    
                    pos_data = parse_degree(position_str)
                    if pos_data:
                        result["houses"][house_num] = {
                            "sign": pos_data["sign"],
                            "degree": pos_data["degree"],
                            "formatted": pos_data["formatted"]
                        }
        
        # Parse special points (Ascendant, MC, etc.)
        elif line.startswith("Ascendant") or line.startswith("MC"):
            # Example: Ascendant       24 cp 23'49.2728  392°17'49.4100
            # Example: Ascendant       23 cp 22' 8"  403°44'50"  (note: split seconds)
            parts = line.split()
            point_name = parts[0]
            if len(parts) >= 4:
                # Check for split seconds like "22'" and "8""
                if len(parts) >= 5 and parts[3].endswith("'") and parts[4][0].isdigit():
                    # Minutes and seconds split: "22'" and "8""
                    position_str = f"{parts[1]} {parts[2]} {parts[3]} {parts[4]}"
                else:
                    # Normal format: minutes'seconds together
                    position_str = f"{parts[1]} {parts[2]} {parts[3]}"
                
                pos_data = parse_degree(position_str)
                if pos_data:
                    result["points"][point_name] = {
                        "sign": pos_data["sign"],
                        "degree": pos_data["degree"],
                        "formatted": pos_data["formatted"]
                    }
    
    # Validate that we got meaningful data
    # Real swetest output ALWAYS contains both planets and houses
    if not result["planets"] or not result["houses"]:
        raise SweetestParseError(
            "Missing planets or houses in swetest output. "
            "Output may be incomplete or from an error."
        )
    
    return result
