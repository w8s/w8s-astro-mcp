"""SQLAlchemy models for w8s-astro-mcp.

This package contains all database models:
- Profile: Birth data and cached natal charts
- TransitLookup: History of transit calculations

Example usage:
    from w8s_astro_mcp.models import Profile, TransitLookup
    from w8s_astro_mcp.database import get_session
    
    with get_session() as session:
        profile = Profile(
            name="Todd",
            birth_date="1981-05-06",
            birth_time="00:50",
            birth_location_name="St. Louis, MO",
            birth_latitude=38.627003,
            birth_longitude=-90.199402,
            birth_timezone="America/Chicago",
            is_primary=True
        )
        session.add(profile)
"""

from w8s_astro_mcp.models.profile import Profile
from w8s_astro_mcp.models.transit_lookup import TransitLookup

__all__ = [
    "Profile",
    "TransitLookup",
]
