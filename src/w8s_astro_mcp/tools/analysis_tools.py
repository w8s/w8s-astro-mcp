"""Analysis tools for astrological calculations."""

import json
from datetime import datetime, timedelta
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
                "applying": None  # filled in by compare_charts() via aspect_motion()
            }
    
    return None


# Values accepted by include_angles (see compare_charts).
INCLUDE_ANGLES_MODES = ("none", "natal", "transit", "both")

# Relative speeds below this (degrees/day) count as stationary: no direction is reported.
MIN_RELATIVE_SPEED = 0.001


def _wrap(angle: float) -> float:
    """Normalise an angle to the range (-180, 180]."""
    wrapped = angle % 360.0
    if wrapped > 180.0:
        wrapped -= 360.0
    return wrapped


def signed_separation(pos1: float, pos2: float) -> float:
    """
    Signed angular distance from pos1 to pos2, normalised to (-180, 180].

    Positive means pos2 is ahead of pos1 (counter-clockwise on the zodiac wheel).
    """
    return _wrap(pos2 - pos1)


def aspect_motion(
    pos1: float,
    speed1: Optional[float],
    pos2: float,
    speed2: Optional[float],
    exact_angle: float,
) -> Tuple[Optional[bool], Optional[float]]:
    """
    Work out whether an aspect is applying or separating, and when it is exact.

    Args:
        pos1: Absolute position (0-360) of the first body.
        speed1: Its speed in degrees/day (negative = retrograde), or None if fixed/unknown.
        pos2: Absolute position (0-360) of the second body.
        speed2: Its speed in degrees/day, or None if fixed/unknown.
        exact_angle: The aspect's exact angle (0, 30, 45, 60, 90, 120, 135, 150, 180).

    Returns:
        (applying, days_to_exact):
          - applying: True while the aspect is tightening, False once it is loosening,
            None when direction cannot be determined.
          - days_to_exact: signed days until exact (negative = exact already passed),
            estimated linearly from the current speeds. None when direction is unknown.

    A body with no speed is treated as fixed (e.g. a natal point). If neither body has a
    speed, or their relative speed is below MIN_RELATIVE_SPEED (stationary), both values
    are None. An aspect that is exactly perfect right now returns (None, 0.0).

    The estimate ignores acceleration, so it is unreliable for the Moon (hours, not days)
    and for planets close to a station.
    """
    if speed1 is None and speed2 is None:
        return None, None

    relative_speed = (speed2 or 0.0) - (speed1 or 0.0)
    if abs(relative_speed) < MIN_RELATIVE_SPEED:
        return None, None

    separation = signed_separation(pos1, pos2)
    # An aspect is exact when the separation equals +exact or -exact; the pair is
    # heading for whichever of the two is nearer.
    error = min(
        (_wrap(separation - exact_angle), _wrap(separation + exact_angle)),
        key=abs,
    )
    if abs(error) < 1e-9:
        return None, 0.0

    days_to_exact = -error / relative_speed
    return days_to_exact > 0, days_to_exact


def chart_labels(
    chart1_meta: Optional[Dict[str, Any]],
    chart2_meta: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Human-readable labels for the two charts being compared.

    Uses each chart's ``kind`` ("natal", "transit", "event:<label>"). When both charts
    are the same kind (e.g. synastry) the labels are disambiguated with the profile
    ``name`` if both are known and different, otherwise with "chart 1" / "chart 2".
    With no metadata at all the labels are "chart 1" and "chart 2".
    """
    meta1 = chart1_meta or {}
    meta2 = chart2_meta or {}
    kind1 = meta1.get("kind") or "chart 1"
    kind2 = meta2.get("kind") or "chart 2"

    if kind1 != kind2:
        return kind1, kind2

    name1, name2 = meta1.get("name"), meta2.get("name")
    if name1 and name2 and name1 != name2:
        return f"{kind1} ({name1})", f"{kind2} ({name2})"
    return f"{kind1}, chart 1", f"{kind2}, chart 2"


def _resolve_include_angles(include_angles: Optional[str], planets_only: bool) -> str:
    """Effective angle mode. ``include_angles`` wins; ``planets_only`` is the legacy alias."""
    if include_angles is not None:
        if include_angles not in INCLUDE_ANGLES_MODES:
            raise AnalysisError(
                "include_angles must be one of: " + ", ".join(INCLUDE_ANGLES_MODES)
            )
        return include_angles
    return "none" if planets_only else "both"


def _uses_points(mode: str, kind: Optional[str]) -> bool:
    """Whether a chart of this kind contributes its angles/points under this mode."""
    if mode == "both":
        return True
    if mode == "natal":
        return kind == "natal"
    if mode == "transit":
        return kind == "transit"
    return False


def _exact_utc(reference_chart: Optional[Dict[str, Any]], days_to_exact: Optional[float]) -> Optional[str]:
    """
    ISO-8601 UTC timestamp (rounded to the minute) of the exact hit, or None.

    ``reference_chart`` is the chart whose planets are moving; its metadata date/time
    (UT, as the ephemeris interprets it) is the moment ``days_to_exact`` is measured from.
    """
    if days_to_exact is None or not reference_chart:
        return None
    meta = reference_chart.get("metadata") or {}
    try:
        base = datetime.strptime(str(meta["date"]), "%Y-%m-%d")
        hours, minutes = str(meta["time"]).split(":")[:2]
        base = base.replace(hour=int(hours), minute=int(minutes))
    except (KeyError, ValueError, TypeError):
        return None
    moment = base + timedelta(days=days_to_exact)
    moment = (moment + timedelta(seconds=30)).replace(second=0, microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _describe_chart(
    chart: Dict[str, Any],
    meta: Optional[Dict[str, Any]],
    label: str,
) -> Dict[str, Any]:
    """Chart descriptor used in result metadata (JSON-safe)."""
    chart_meta = chart.get("metadata") or {}
    date = chart_meta.get("date")
    time = chart_meta.get("time")
    return {
        "kind": (meta or {}).get("kind"),
        "label": label,
        "name": (meta or {}).get("name"),
        "date": None if date is None else str(date),
        "time": None if time is None else str(time),
    }


def compare_charts(
    chart1: Dict[str, Any],
    chart2: Dict[str, Any],
    orb_multiplier: float = 1.0,
    planets_only: bool = True,
    include_angles: Optional[str] = None,
    chart1_meta: Optional[Dict[str, Any]] = None,
    chart2_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate aspects between two charts (synastry or transits).

    Args:
        chart1: First chart data (natal or transit)
        chart2: Second chart data (transit or natal)
        orb_multiplier: Multiplier for aspect orbs (default 1.0)
        planets_only: Legacy switch. True (default) compares planets only; False also
            compares the angles/points of both charts. Ignored when include_angles is given.
        include_angles: "none" | "natal" | "transit" | "both". Which charts contribute
            their angles/points (Ascendant, MC, ...). "natal" and "transit" use the chart
            kinds given in chart1_meta / chart2_meta. Overrides planets_only.
        chart1_meta: Optional descriptor for chart1: {"kind": "natal"|"transit"|"event:<label>",
            "name": <profile name>}. Used for labels and include_angles.
        chart2_meta: Same, for chart2.

    Returns:
        Dictionary containing:
        - aspects: List of aspect dictionaries. Each has the original keys plus
          applying, days_to_exact, exact_utc, body1_chart, body2_chart,
          body1_speed and body2_speed.
        - metadata: Info about the comparison.

    Example chart structure:
        {
            "planets": {
                "Sun": {"degree": 14.66, "sign": "Aquarius", "speed": 1.01},
                "Moon": {"degree": 23.9, "sign": "Aquarius"}
            },
            "houses": {
                "1": {"degree": 10.5, "sign": "Scorpio"}
            },
            "metadata": {"date": "2026-02-07", "time": "12:00:00"}
        }

    ``speed`` (degrees/day, negative = retrograde) is optional; it enables the
    applying/separating estimate. Bodies without it are treated as fixed.
    """
    mode = _resolve_include_angles(include_angles, planets_only)
    label1, label2 = chart_labels(chart1_meta, chart2_meta)
    kind1 = (chart1_meta or {}).get("kind")
    kind2 = (chart2_meta or {}).get("kind")

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
    if _uses_points(mode, kind1) and "points" in chart1:
        chart1_bodies.update(chart1["points"])
    if _uses_points(mode, kind2) and "points" in chart2:
        chart2_bodies.update(chart2["points"])

    # Calculate all aspects
    for body1_name, body1_data in chart1_bodies.items():
        if "degree" not in body1_data or "sign" not in body1_data:
            continue

        pos1 = get_absolute_position(body1_data["degree"], body1_data["sign"])
        speed1 = body1_data.get("speed")

        for body2_name, body2_data in chart2_bodies.items():
            if "degree" not in body2_data or "sign" not in body2_data:
                continue

            pos2 = get_absolute_position(body2_data["degree"], body2_data["sign"])
            speed2 = body2_data.get("speed")

            # Calculate angle
            angle = calculate_aspect_angle(pos1, pos2)

            # Check if it forms an aspect
            aspect_info = identify_aspect(angle, orb_multiplier)

            if aspect_info:
                applying, days_to_exact = aspect_motion(
                    pos1, speed1, pos2, speed2, aspect_info["exact_angle"]
                )
                # The chart whose bodies are moving is the reference for timestamps.
                reference = chart2 if speed2 is not None else chart1
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
                    "orb_used": aspect_info["orb_used"],
                    "applying": applying,
                    "days_to_exact": days_to_exact,
                    "exact_utc": _exact_utc(reference, days_to_exact),
                    "body1_chart": label1,
                    "body2_chart": label2,
                    "body1_speed": speed1,
                    "body2_speed": speed2,
                })

    # Sort by orb (tightest first)
    aspects.sort(key=lambda x: x["orb"])

    return {
        "aspects": aspects,
        "metadata": {
            "chart1_date": chart1.get("metadata", {}).get("date", "unknown"),
            "chart2_date": chart2.get("metadata", {}).get("date", "unknown"),
            "orb_multiplier": orb_multiplier,
            "planets_only": mode == "none",
            "include_angles": mode,
            "chart1": _describe_chart(chart1, chart1_meta, label1),
            "chart2": _describe_chart(chart2, chart2_meta, label2),
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


def _motion_text(aspect: Dict[str, Any]) -> str:
    """
    Motion summary for the appended report line, e.g.
    "separating · exact ~0.6 days ago (≈ 2026-09-18 19:24 UT)". Empty when unknown.
    """
    parts = []

    applying = aspect.get("applying")
    if applying is True:
        parts.append("applying")
    elif applying is False:
        parts.append("separating")

    days = aspect.get("days_to_exact")
    if days is not None:
        if abs(days) < 0.02:
            parts.append("exact now")
        else:
            amount = "<0.1" if abs(days) < 0.05 else f"~{abs(days):.1f}"
            phrase = f"exact in {amount} days" if days > 0 else f"exact {amount} days ago"
            exact_utc = aspect.get("exact_utc")
            if exact_utc:
                phrase += f" (≈ {exact_utc[:10]} {exact_utc[11:16]} UT)"
            parts.append(phrase)

    return " · ".join(parts)


def _chart_line(aspect: Dict[str, Any]) -> str:
    """The one line appended to each aspect: chart labels plus motion."""
    line = (
        f"{aspect['body1']} = {aspect.get('body1_chart', 'chart 1')}"
        f" · {aspect['body2']} = {aspect.get('body2_chart', 'chart 2')}"
    )
    motion = _motion_text(aspect)
    if motion:
        line += " · " + motion
    return line


def format_aspect_report(comparison_result: Dict[str, Any]) -> str:
    """
    Format comparison results into a readable report.

    Each aspect keeps its original four lines; a fifth line names the chart each body
    belongs to and, when known, whether the aspect is applying or separating.

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
        report += f"  Orb: {orb:.2f}°\n"
        report += f"  {_chart_line(aspect)}\n\n"

    return report


def _round(value: Optional[float], places: int) -> Optional[float]:
    return None if value is None else round(value, places)


def _json_body(aspect: Dict[str, Any], index: int) -> Dict[str, Any]:
    """One body of an aspect as a JSON-safe dict (index is 1 or 2)."""
    position = aspect[f"body{index}_position"]
    return {
        "name": aspect[f"body{index}"],
        "chart": aspect.get(f"body{index}_chart", f"chart {index}"),
        "chart_index": index,
        "sign": position["sign"],
        "degree": _round(position["degree"], 4),
        "absolute": _round(position["absolute"], 4),
        "speed": _round(aspect.get(f"body{index}_speed"), 4),
    }


def format_aspect_json(comparison_result: Dict[str, Any]) -> str:
    """
    Format comparison results as a JSON string.

    Numbers stay numbers (degrees, degrees/day, days); there are no glyphs, wikilinks or
    display strings, so callers decide how to present the data.

    Args:
        comparison_result: Output from compare_charts()

    Returns:
        Pretty-printed JSON string with "metadata" and "aspects" keys.
    """
    metadata = comparison_result["metadata"]
    payload = {
        "metadata": {
            "chart1": metadata.get("chart1"),
            "chart2": metadata.get("chart2"),
            "orb_multiplier": metadata["orb_multiplier"],
            "include_angles": metadata.get("include_angles", "none"),
            "total_aspects": metadata["total_aspects"],
        },
        "aspects": [
            {
                "aspect": a["aspect"],
                "exact_angle": a["exact_angle"],
                "actual_angle": _round(a["actual_angle"], 4),
                "orb": _round(a["orb"], 4),
                "orb_used": _round(a["orb_used"], 4),
                "applying": a.get("applying"),
                "days_to_exact": _round(a.get("days_to_exact"), 3),
                "exact_utc": a.get("exact_utc"),
                "body1": _json_body(a, 1),
                "body2": _json_body(a, 2),
            }
            for a in comparison_result["aspects"]
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


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
