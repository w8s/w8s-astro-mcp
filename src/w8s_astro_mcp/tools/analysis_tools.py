"""Analysis tools for astrological calculations."""

from typing import Dict, Any, List, Optional, Tuple


class AnalysisError(Exception):
    """Raised when analysis fails."""
    pass


# Zodiac sign positions (0-based, each sign is 30 degrees)
SIGN_POSITIONS = {
    "Aries": 0,
    "Taurus": 30,
    "Gemini": 60,
    "Cancer": 90,
    "Leo": 120,
    "Virgo": 150,
    "Libra": 180,
    "Scorpio": 210,
    "Sagittarius": 240,
    "Capricorn": 270,
    "Aquarius": 300,
    "Pisces": 330
}

# Aspect definitions with orbs
ASPECTS = {
    "conjunction": {"angle": 0, "orb": 8},
    "opposition": {"angle": 180, "orb": 8},
    "trine": {"angle": 120, "orb": 8},
    "square": {"angle": 90, "orb": 8},
    "sextile": {"angle": 60, "orb": 6},
    "quincunx": {"angle": 150, "orb": 3},
    "semi-sextile": {"angle": 30, "orb": 2},
    "semi-square": {"angle": 45, "orb": 2},
    "sesquiquadrate": {"angle": 135, "orb": 2}
}


def get_absolute_position(degree: float, sign: str) -> float:
    """
    Convert sign + degree to absolute zodiac position (0-360).
    
    Args:
        degree: Degree within the sign (0-30)
        sign: Zodiac sign name
    
    Returns:
        Absolute position in degrees (0-360)
        
    Raises:
        AnalysisError: If sign is not recognized
    """
    if sign not in SIGN_POSITIONS:
        raise AnalysisError(f"Unknown zodiac sign: {sign}")
    
    return SIGN_POSITIONS[sign] + degree


def calculate_aspect_angle(pos1: float, pos2: float) -> float:
    """
    Calculate the shortest angle between two zodiac positions.
    
    Args:
        pos1: First position in degrees (0-360)
        pos2: Second position in degrees (0-360)
    
    Returns:
        Shortest angle in degrees (0-180)
    """
    diff = abs(pos1 - pos2)
    # Find shortest distance around circle
    if diff > 180:
        diff = 360 - diff
    return diff


def identify_aspect(angle: float, orb_multiplier: float = 1.0) -> Optional[Dict[str, Any]]:
    """
    Identify what aspect (if any) an angle represents.
    
    Args:
        angle: Angle in degrees
        orb_multiplier: Multiplier for orbs (default 1.0)
    
    Returns:
        Dict with aspect info or None if no aspect found
        Contains: name, exact_angle, actual_angle, orb, orb_used
    """
    for aspect_name, aspect_data in ASPECTS.items():
        exact_angle = aspect_data["angle"]
        orb = aspect_data["orb"] * orb_multiplier
        
        diff = abs(angle - exact_angle)
        if diff <= orb:
            return {
                "name": aspect_name,
                "exact_angle": exact_angle,
                "actual_angle": angle,
                "orb": diff,
                "orb_used": orb,
                "applying": None  # Can be calculated with speed data
            }
    
    return None


def compare_charts(
    chart1: Dict[str, Any],
    chart2: Dict[str, Any],
    orb_multiplier: float = 1.0,
    planets_only: bool = True
) -> Dict[str, Any]:
    """
    Calculate aspects between two charts (synastry or transits).
    
    Args:
        chart1: First chart data (natal or transit)
        chart2: Second chart data (transit or natal)
        orb_multiplier: Multiplier for aspect orbs (default 1.0)
        planets_only: If True, only compare planets (default True)
    
    Returns:
        Dictionary containing:
        - aspects: List of aspect dictionaries
        - metadata: Info about the comparison
    
    Example chart structure:
        {
            "planets": {
                "Sun": {"degree": 14.66, "sign": "Aquarius"},
                "Moon": {"degree": 23.9, "sign": "Aquarius"}
            },
            "houses": {
                "1": {"degree": 10.5, "sign": "Scorpio"}
            },
            "metadata": {"date": "2026-02-07", "time": "12:00:00"}
        }
    """
    aspects = []
    
    # Get bodies to compare
    chart1_bodies = {}
    chart2_bodies = {}
    
    # Add planets
    if "planets" in chart1:
        chart1_bodies.update(chart1["planets"])
    if "planets" in chart2:
        chart2_bodies.update(chart2["planets"])
    
    # Optionally add points (Ascendant, MC, etc.)
    if not planets_only:
        if "points" in chart1:
            chart1_bodies.update(chart1["points"])
        if "points" in chart2:
            chart2_bodies.update(chart2["points"])
    
    # Calculate all aspects
    for body1_name, body1_data in chart1_bodies.items():
        if "degree" not in body1_data or "sign" not in body1_data:
            continue
            
        pos1 = get_absolute_position(body1_data["degree"], body1_data["sign"])
        
        for body2_name, body2_data in chart2_bodies.items():
            if "degree" not in body2_data or "sign" not in body2_data:
                continue
            
            pos2 = get_absolute_position(body2_data["degree"], body2_data["sign"])
            
            # Calculate angle
            angle = calculate_aspect_angle(pos1, pos2)
            
            # Check if it forms an aspect
            aspect_info = identify_aspect(angle, orb_multiplier)
            
            if aspect_info:
                aspects.append({
                    "body1": body1_name,
                    "body1_position": {
                        "degree": body1_data["degree"],
                        "sign": body1_data["sign"],
                        "absolute": pos1
                    },
                    "body2": body2_name,
                    "body2_position": {
                        "degree": body2_data["degree"],
                        "sign": body2_data["sign"],
                        "absolute": pos2
                    },
                    "aspect": aspect_info["name"],
                    "exact_angle": aspect_info["exact_angle"],
                    "actual_angle": aspect_info["actual_angle"],
                    "orb": aspect_info["orb"],
                    "orb_used": aspect_info["orb_used"]
                })
    
    # Sort by orb (tightest first)
    aspects.sort(key=lambda x: x["orb"])
    
    return {
        "aspects": aspects,
        "metadata": {
            "chart1_date": chart1.get("metadata", {}).get("date", "unknown"),
            "chart2_date": chart2.get("metadata", {}).get("date", "unknown"),
            "orb_multiplier": orb_multiplier,
            "planets_only": planets_only,
            "total_aspects": len(aspects)
        }
    }


def find_planets_in_houses(
    planets: Dict[str, Any],
    houses: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determine which house each planet is in.
    
    Args:
        planets: Dictionary of planet positions
            {"Sun": {"degree": 14.66, "sign": "Aquarius"}, ...}
        houses: Dictionary of house cusps
            {"1": {"degree": 10.5, "sign": "Scorpio"}, ...}
    
    Returns:
        Dictionary containing:
        - placements: Dict mapping planet -> house number
        - houses_populated: Dict mapping house number -> list of planets
        - metadata: Info about the calculation
    
    Note:
        Uses whole sign houses if house cusps follow sign boundaries.
        Otherwise calculates based on cusp positions.
    """
    placements = {}
    houses_populated = {str(i): [] for i in range(1, 13)}
    
    # Convert house cusps to absolute positions
    house_positions = []
    
    # Debug: Check what keys we actually have
    if not houses:
        raise AnalysisError("Houses dictionary is empty")
    
    for house_num in range(1, 13):
        house_key = str(house_num)  # Always use string keys
        
        if house_key not in houses:
            # Debug info about available keys
            available_keys = list(houses.keys())
            key_types = {type(k).__name__ for k in available_keys}
            sample_keys = available_keys[:3]
            raise AnalysisError(
                f"Missing house cusp for house {house_num}. "
                f"Available keys (sample): {sample_keys}, "
                f"Key types: {key_types}, "
                f"Total houses: {len(available_keys)}"
            )
        
        house_data = houses[house_key]
        if "degree" not in house_data or "sign" not in house_data:
            raise AnalysisError(f"Invalid house data for house {house_num}")
        
        abs_pos = get_absolute_position(house_data["degree"], house_data["sign"])
        house_positions.append({
            "number": house_num,
            "position": abs_pos,
            "sign": house_data["sign"]
        })
    
    # Sort houses by position to handle wrapping
    house_positions.sort(key=lambda x: x["position"])
    
    # Find which house each planet is in
    for planet_name, planet_data in planets.items():
        if "degree" not in planet_data or "sign" not in planet_data:
            continue
        
        planet_pos = get_absolute_position(planet_data["degree"], planet_data["sign"])
        
        # Find the house by determining which house cusp is before this planet
        house_num = None
        
        for i, house_info in enumerate(house_positions):
            next_house = house_positions[(i + 1) % 12]
            
            # Handle wrapping at 360/0 degrees
            if house_info["position"] < next_house["position"]:
                # Normal case: planet between this cusp and next
                if house_info["position"] <= planet_pos < next_house["position"]:
                    house_num = house_info["number"]
                    break
            else:
                # Wrapping case: house crosses 0 degrees
                if planet_pos >= house_info["position"] or planet_pos < next_house["position"]:
                    house_num = house_info["number"]
                    break
        
        if house_num is None:
            # Fallback: assign to first house
            house_num = 1
        
        placements[planet_name] = house_num
        houses_populated[str(house_num)].append(planet_name)
    
    return {
        "placements": placements,
        "houses_populated": houses_populated,
        "metadata": {
            "total_planets": len(placements),
            "houses_with_planets": sum(1 for planets in houses_populated.values() if planets)
        }
    }


def format_aspect_report(comparison_result: Dict[str, Any]) -> str:
    """
    Format comparison results into a readable report.
    
    Args:
        comparison_result: Output from compare_charts()
    
    Returns:
        Formatted string report
    """
    report = "# Aspect Analysis\n\n"
    
    metadata = comparison_result["metadata"]
    report += f"Chart 1: {metadata['chart1_date']}\n"
    report += f"Chart 2: {metadata['chart2_date']}\n"
    report += f"Total Aspects Found: {metadata['total_aspects']}\n"
    report += f"Orb Multiplier: {metadata['orb_multiplier']}\n\n"
    
    if not comparison_result["aspects"]:
        report += "No aspects found within orb limits.\n"
        return report
    
    report += "## Aspects (sorted by tightness)\n\n"
    
    for aspect in comparison_result["aspects"]:
        body1 = aspect["body1"]
        body2 = aspect["body2"]
        aspect_name = aspect["aspect"].title()
        orb = aspect["orb"]
        
        pos1 = aspect["body1_position"]
        pos2 = aspect["body2_position"]
        
        report += f"**{body1}** {aspect_name} **{body2}**\n"
        report += f"  {body1}: {pos1['degree']:.2f}° {pos1['sign']}\n"
        report += f"  {body2}: {pos2['degree']:.2f}° {pos2['sign']}\n"
        report += f"  Orb: {orb:.2f}°\n\n"
    
    return report


def format_house_report(house_result: Dict[str, Any]) -> str:
    """
    Format house placement results into a readable report.
    
    Args:
        house_result: Output from find_planets_in_houses()
    
    Returns:
        Formatted string report
    """
    report = "# House Placements\n\n"
    
    metadata = house_result["metadata"]
    report += f"Total Planets: {metadata['total_planets']}\n"
    report += f"Houses with Planets: {metadata['houses_with_planets']}\n\n"
    
    report += "## By House\n\n"
    
    for house_num in range(1, 13):
        house_key = str(house_num)
        planets = house_result["houses_populated"][house_key]
        
        if planets:
            planet_list = ", ".join(planets)
            report += f"**House {house_num}**: {planet_list}\n"
        else:
            report += f"**House {house_num}**: (empty)\n"
    
    report += "\n## By Planet\n\n"
    
    for planet, house_num in sorted(house_result["placements"].items()):
        report += f"**{planet}**: House {house_num}\n"
    
    return report
