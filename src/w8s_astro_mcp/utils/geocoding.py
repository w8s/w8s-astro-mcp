"""Geocoding helper to convert location names to coordinates."""

import json
from typing import Optional, Dict, Any
import urllib.request
import urllib.parse


def geocode_location(location_name: str) -> Optional[Dict[str, Any]]:
    """
    Look up coordinates for a location using Nominatim (OpenStreetMap).
    
    Args:
        location_name: Location like "Richardson, TX" or "New York, NY"
        
    Returns:
        Dict with name, latitude, longitude, and suggested timezone, or None if not found
    """
    try:
        # URL encode the location
        encoded_location = urllib.parse.quote(location_name)
        
        # Use Nominatim API (OpenStreetMap's geocoding service)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded_location}&format=json&limit=1"
        
        # Make request with proper headers
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'w8s-astro-mcp/0.1.0'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
        
        if not data:
            return None
        
        result = data[0]
        
        # Extract coordinates
        lat = float(result['lat'])
        lon = float(result['lon'])
        
        # Guess timezone based on longitude (rough approximation)
        # This is a simplified version - for production, use a proper timezone lookup
        tz = guess_timezone_from_coords(lat, lon)
        
        return {
            "name": result.get('display_name', location_name),
            "latitude": lat,
            "longitude": lon,
            "timezone": tz
        }
    
    except Exception:
        return None


def guess_timezone_from_coords(lat: float, lon: float) -> str:
    """
    Rough timezone guess based on longitude.
    For production, use a proper timezone library.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Timezone string (rough approximation)
    """
    # US timezones (very rough)
    if 24 <= lat <= 50 and -125 <= lon <= -65:  # Continental US
        if lon < -120:
            return "America/Los_Angeles"
        elif lon < -105:
            return "America/Denver"
        elif lon < -90:
            return "America/Chicago"
        else:
            return "America/New_York"
    
    # Default to UTC
    return "UTC"
