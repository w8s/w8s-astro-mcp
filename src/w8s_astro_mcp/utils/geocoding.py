"""Geocoding helper to convert location names to coordinates."""

import json
from typing import Optional, Dict, Any
import urllib.request
import urllib.parse

from timezonefinder import TimezoneFinder

# Module-level instance — initialization loads polygon data once
_tf = TimezoneFinder()


def get_timezone_for_coords(lat: float, lon: float) -> str:
    """
    Return the IANA timezone string for any coordinates on earth.

    Uses timezonefinder's full polygon dataset — accurate to timezone borders,
    not just a rough longitude estimate. Falls back to UTC if coordinates are
    over open ocean with no timezone polygon (rare).

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees

    Returns:
        IANA timezone string, e.g. 'Asia/Bangkok', 'America/Chicago', 'UTC'
    """
    tz = _tf.timezone_at(lat=lat, lng=lon)
    return tz if tz else "UTC"


def geocode_location(location_name: str) -> Optional[Dict[str, Any]]:
    """
    Look up coordinates and timezone for a location name using Nominatim (OpenStreetMap).

    Args:
        location_name: Anything Nominatim understands — city, address, country, etc.
                       e.g. "Bangkok, Thailand", "Seattle, WA", "Richardson, TX"

    Returns:
        Dict with name, latitude, longitude, and timezone, or None if not found.
    """
    try:
        encoded_location = urllib.parse.quote(location_name)
        url = (
            f"https://nominatim.openstreetmap.org/search"
            f"?q={encoded_location}&format=json&limit=1"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "w8s-astro-mcp/1.0.0"}
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if not data:
            return None

        result = data[0]
        lat = float(result["lat"])
        lon = float(result["lon"])

        return {
            "name": result.get("display_name", location_name),
            "latitude": lat,
            "longitude": lon,
            "timezone": get_timezone_for_coords(lat, lon),
        }

    except Exception:
        return None
