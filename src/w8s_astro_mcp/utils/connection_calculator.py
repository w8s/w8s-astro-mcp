"""Connection chart calculation engine for Phase 7.

Provides two chart calculation methods:

COMPOSITE CHART
  Each planet position is the circular mean of absolute positions (0-360°)
  across all member natal charts. Circular averaging is required because
  naive averaging of e.g. 350° and 10° would give 180° instead of 0°.
  Houses/points use the same circular mean approach.

DAVISON CHART
  The midpoint datetime (arithmetic mean of birth datetimes expressed as
  Unix timestamps) and midpoint location (arithmetic mean of birth lat/lng)
  define a real moment in time and space. A real swetest call is made for
  that moment, so the Davison chart is a genuine chart, not just averaged
  positions. The midpoint datetime and location are stored in ConnectionChart
  so the chart can be verified and re-cast if needed.

Both methods scale cleanly to N members (not just pairs).

References:
  - Composite: https://en.wikipedia.org/wiki/Composite_chart
  - Davison: https://en.wikipedia.org/wiki/Davison_relationship_chart
  - Circular mean: https://en.wikipedia.org/wiki/Circular_mean
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional
from zoneinfo import ZoneInfo

from ..models import (
    Profile, Location, HouseSystem,
    NatalPlanet, NatalHouse, NatalPoint,
    ConnectionChart, ConnectionPlanet, ConnectionHouse, ConnectionPoint,
)


# ---------------------------------------------------------------------------
# Circular mean helper
# ---------------------------------------------------------------------------

def circular_mean_degrees(angles: List[float]) -> float:
    """
    Compute the circular mean of a list of angles in degrees.

    Handles the wraparound at 0°/360° correctly. For example:
        circular_mean_degrees([350.0, 10.0]) → 0.0
        circular_mean_degrees([90.0, 270.0]) → 0.0  (opposite points cancel)

    Args:
        angles: List of angles in degrees (0.0–360.0)

    Returns:
        Circular mean in degrees (0.0–360.0), always non-negative

    Raises:
        ValueError: If the list is empty
    """
    if not angles:
        raise ValueError("Cannot compute circular mean of empty list")

    sin_sum = sum(math.sin(math.radians(a)) for a in angles)
    cos_sum = sum(math.cos(math.radians(a)) for a in angles)
    mean_rad = math.atan2(sin_sum, cos_sum)
    mean_deg = math.degrees(mean_rad) % 360.0
    # Normalize: floating point can produce exactly 360.0 from % 360.0
    if mean_deg == 360.0:
        mean_deg = 0.0
    return mean_deg


def degrees_to_sign_components(absolute_position: float) -> Tuple[str, int, int, float]:
    """
    Convert an absolute ecliptic position (0-360°) into sign components.

    Args:
        absolute_position: 0.0–360.0

    Returns:
        (sign_name, degree_within_sign, minutes, seconds)
    """
    SIGN_NAMES = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]

    pos = absolute_position % 360.0
    sign_index = int(round(pos, 10) // 30)  # round to 10dp to avoid float boundary errors
    sign = SIGN_NAMES[sign_index]

    within_sign = pos - (sign_index * 30.0)
    degree = int(within_sign)
    remainder_minutes = (within_sign - degree) * 60
    minutes = int(remainder_minutes)
    seconds = (remainder_minutes - minutes) * 60

    return sign, degree, minutes, seconds


# ---------------------------------------------------------------------------
# Composite chart calculation
# ---------------------------------------------------------------------------

def calculate_composite_positions(
    natal_charts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate composite chart planet positions from N natal charts.

    Each planet's absolute position is circularly averaged across all charts.
    If a planet is missing from any chart it is excluded from the composite.

    Args:
        natal_charts: List of natal chart dicts (from db_helpers.get_natal_chart_data)
                      Each must have 'planets' key with planet dicts containing
                      'absolute_position' or reconstructible from degree+sign.

    Returns:
        Dict with keys:
          'planets': {planet_name: {absolute_position, sign, degree, minutes, seconds}}
          'houses':  {house_num_str: {absolute_position, sign, degree, minutes, seconds}}
          'points':  {point_type: {absolute_position, sign, degree, minutes, seconds}}

    Raises:
        ValueError: If natal_charts is empty or has fewer than 2 members
    """
    if len(natal_charts) < 2:
        raise ValueError("Composite chart requires at least 2 natal charts")

    result: Dict[str, Any] = {"planets": {}, "houses": {}, "points": {}}

    # --- Planets ---
    # Collect all planet names present in ALL charts (intersection)
    all_planet_names = set(natal_charts[0]["planets"].keys())
    for chart in natal_charts[1:]:
        all_planet_names &= set(chart["planets"].keys())

    for planet_name in sorted(all_planet_names):
        positions = []
        for chart in natal_charts:
            p = chart["planets"][planet_name]
            positions.append(p["absolute_position"])

        avg = circular_mean_degrees(positions)
        sign, degree, minutes, seconds = degrees_to_sign_components(avg)
        result["planets"][planet_name] = {
            "absolute_position": avg,
            "sign": sign,
            "degree": degree,
            "minutes": minutes,
            "seconds": seconds,
        }

    # --- Houses ---
    # Use string keys ("1"-"12") to match the rest of the codebase
    all_house_keys = set(natal_charts[0]["houses"].keys())
    for chart in natal_charts[1:]:
        all_house_keys &= set(chart["houses"].keys())

    for house_key in sorted(all_house_keys, key=lambda x: int(x)):
        positions = []
        for chart in natal_charts:
            h = chart["houses"][house_key]
            positions.append(h["absolute_position"])

        avg = circular_mean_degrees(positions)
        sign, degree, minutes, seconds = degrees_to_sign_components(avg)
        result["houses"][house_key] = {
            "absolute_position": avg,
            "sign": sign,
            "degree": degree,
            "minutes": minutes,
            "seconds": seconds,
        }

    # --- Points (ASC, MC, etc.) ---
    all_point_keys = set(natal_charts[0]["points"].keys())
    for chart in natal_charts[1:]:
        all_point_keys &= set(chart["points"].keys())

    for point_key in sorted(all_point_keys):
        positions = []
        for chart in natal_charts:
            pt = chart["points"][point_key]
            positions.append(pt["absolute_position"])

        avg = circular_mean_degrees(positions)
        sign, degree, minutes, seconds = degrees_to_sign_components(avg)
        result["points"][point_key] = {
            "absolute_position": avg,
            "sign": sign,
            "degree": degree,
            "minutes": minutes,
            "seconds": seconds,
        }

    return result


# ---------------------------------------------------------------------------
# Davison chart calculation
# ---------------------------------------------------------------------------

def calculate_davison_midpoint(
    profiles: List[Profile],
    locations: List[Location],
) -> Dict[str, Any]:
    """
    Calculate the Davison midpoint datetime and location from N profiles.

    The midpoint datetime is the arithmetic mean of all birth datetimes
    (expressed as Unix timestamps, then converted back to a datetime).
    The midpoint location is the arithmetic mean of all birth lat/lng values.

    Args:
        profiles: List of Profile objects (must have birth_date, birth_time)
        locations: List of corresponding birth Location objects (same order)

    Returns:
        Dict with keys:
          'date': str (YYYY-MM-DD)
          'time': str (HH:MM)
          'latitude': float
          'longitude': float
          'timezone': str ('UTC' — Davison datetime is always expressed in UTC)

    Raises:
        ValueError: If fewer than 2 profiles, or profiles/locations mismatch

    Note on timezones:
        birth_time is a local clock reading (e.g. "14:30" in Chicago).
        Each birth datetime is converted to UTC using the birth location's
        timezone before averaging, so the midpoint is a true absolute moment.
    """
    if len(profiles) < 2:
        raise ValueError("Davison chart requires at least 2 profiles")
    if len(profiles) != len(locations):
        raise ValueError("profiles and locations lists must be the same length")

    # --- Average birth datetimes (convert local → UTC first) ---
    timestamps = []
    for profile, location in zip(profiles, locations):
        tz = ZoneInfo(location.timezone)
        dt_local = datetime.strptime(
            f"{profile.birth_date} {profile.birth_time}",
            "%Y-%m-%d %H:%M"
        ).replace(tzinfo=tz)
        dt_utc = dt_local.astimezone(timezone.utc)
        timestamps.append(dt_utc.timestamp())

    avg_timestamp = sum(timestamps) / len(timestamps)
    avg_dt = datetime.fromtimestamp(avg_timestamp, tz=timezone.utc)

    # --- Average birth locations ---
    avg_lat = sum(loc.latitude for loc in locations) / len(locations)
    avg_lng = sum(loc.longitude for loc in locations) / len(locations)

    return {
        "date": avg_dt.strftime("%Y-%m-%d"),
        "time": avg_dt.strftime("%H:%M"),
        "latitude": round(avg_lat, 6),
        "longitude": round(avg_lng, 6),
        "timezone": "UTC",
    }


# ---------------------------------------------------------------------------
# Natal chart data enrichment (adds absolute_position for calculation)
# ---------------------------------------------------------------------------

def enrich_natal_chart_for_composite(chart_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure natal chart data has absolute_position on each planet/house/point.

    db_helpers.get_natal_chart_data() returns degree-within-sign, not absolute.
    This function reconstructs absolute_position from sign + degree if missing.

    In practice this should not be needed if the caller pulls NatalPlanet rows
    directly (which have absolute_position), but this guards against stale data.

    Args:
        chart_data: Natal chart dict from get_natal_chart_data()

    Returns:
        Enriched chart_data with absolute_position guaranteed on each entry
    """
    SIGN_OFFSETS = {
        "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90,
        "Leo": 120, "Virgo": 150, "Libra": 180, "Scorpio": 210,
        "Sagittarius": 240, "Capricorn": 270, "Aquarius": 300, "Pisces": 330,
    }

    for planet_name, pdata in chart_data.get("planets", {}).items():
        if "absolute_position" not in pdata:
            offset = SIGN_OFFSETS.get(pdata["sign"], 0)
            pdata["absolute_position"] = offset + pdata["degree"]

    for house_key, hdata in chart_data.get("houses", {}).items():
        if "absolute_position" not in hdata:
            offset = SIGN_OFFSETS.get(hdata["sign"], 0)
            hdata["absolute_position"] = offset + hdata["degree"]

    for point_key, ptdata in chart_data.get("points", {}).items():
        if "absolute_position" not in ptdata:
            offset = SIGN_OFFSETS.get(ptdata["sign"], 0)
            ptdata["absolute_position"] = offset + ptdata["degree"]

    return chart_data
