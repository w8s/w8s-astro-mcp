"""Parser for Swiss Ephemeris (swetest) output."""

import re
from datetime import datetime
from typing import Dict, Any, Optional


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
    Parse a degree string like "14 aq 39'38\"" into components.
    
    Returns:
        dict with 'degree' (float), 'sign' (str), 'formatted' (str)
        Returns None if format is invalid or sign is not recognized
    """
    # Pattern: "14 aq 39'38"" or "14 aq 39' 38"" or "14 aq 39' 8"" (various spacing)
    match = re.match(r"(\d+)\s+([a-z]{2})\s+(\d+)'\s*(\d+)\"", degree_str.strip())
    if not match:
        return None
    
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


def parse_swetest_output(output: str) -> Dict[str, Any]:
    """
    Parse swetest output into structured data.
    
    Args:
        output: Raw output from swetest command
    
    Returns:
        Dictionary with parsed transit data
    """
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
                    # Example: Sun             14 aq 39'38"    1° 0'50"
                    # Example: Mercury         23 aq 54' 3"    1°46'23"
                    parts = line.split()
                    if len(parts) >= 4:
                        # Take up to 5 parts to handle space before seconds
                        position_parts = parts[1:6] if len(parts) >= 6 else parts[1:]
                        position_str = " ".join(position_parts)
                        
                        # Find where declination starts (after the closing quote)
                        quote_idx = position_str.rfind('"')
                        if quote_idx != -1:
                            actual_position = position_str[:quote_idx+1]
                            declination_str = position_str[quote_idx+1:].strip()
                        else:
                            actual_position = position_str
                            declination_str = ""
                        
                        pos_data = parse_degree(actual_position)
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
            # Example: house  1        23 cp 22' 8"  403°44'50"
            match = re.match(r"house\s+(\d+)\s+(.*)", line)
            if match:
                house_num = int(match.group(1))
                rest = match.group(2).strip()
                
                # Handle variable spacing like planets - take enough parts and find quote
                parts = rest.split()
                if len(parts) >= 3:
                    position_parts = parts[0:5] if len(parts) >= 5 else parts
                    position_str = " ".join(position_parts)
                    
                    # Find where position ends (after closing quote)
                    quote_idx = position_str.find('"')
                    if quote_idx != -1:
                        actual_position = position_str[:quote_idx+1]
                        pos_data = parse_degree(actual_position)
                        if pos_data:
                            result["houses"][house_num] = {
                                "sign": pos_data["sign"],
                                "degree": pos_data["degree"],
                                "formatted": pos_data["formatted"]
                            }
        
        # Parse special points (Ascendant, MC, etc.)
        elif line.startswith("Ascendant") or line.startswith("MC"):
            # Example: Ascendant       23 cp 22' 8"  403°44'50"
            parts = line.split()
            point_name = parts[0]
            if len(parts) >= 4:
                # Handle variable spacing
                position_parts = parts[1:6] if len(parts) >= 6 else parts[1:]
                position_str = " ".join(position_parts)
                
                # Find where position ends
                quote_idx = position_str.find('"')
                if quote_idx != -1:
                    actual_position = position_str[:quote_idx+1]
                    pos_data = parse_degree(actual_position)
                    if pos_data:
                        result["points"][point_name] = {
                            "sign": pos_data["sign"],
                            "degree": pos_data["degree"],
                            "formatted": pos_data["formatted"]
                        }
    
    return result
