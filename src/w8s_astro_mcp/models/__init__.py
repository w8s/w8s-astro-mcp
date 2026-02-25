"""SQLAlchemy models for w8s-astro-mcp.

This package contains all database models:
- AppSettings: Application-level configuration (current profile, etc.)
- Profile: Birth data and cached natal charts
- Location: Saved locations (birth, home, custom)
- HouseSystem: Reference data for house systems
- Natal* models: Cached natal chart data
- Transit* models: History of transit calculations
- Connection* models: Relationship charts (composite, Davison) — Phase 7
- Event* models: Charts cast for a moment in time and place — Phase 8

Example usage:
    from w8s_astro_mcp.models import Profile, Location, AppSettings
    from w8s_astro_mcp.database import get_session
    
    with get_session() as session:
        # Create a location
        location = Location(
            label="St. Louis, MO",
            latitude=38.627,
            longitude=-90.198,
            timezone="America/Chicago"
        )
        session.add(location)
        session.flush()
        
        # Create a profile
        profile = Profile(
            name="Todd",
            birth_date="1981-05-06",
            birth_time="00:50",
            birth_location_id=location.id,
            preferred_house_system_id=1  # Placidus
        )
        session.add(profile)
        session.flush()
        
        # Set as current user
        settings = session.query(AppSettings).first()
        settings.current_profile_id = profile.id
        session.commit()
"""

from w8s_astro_mcp.models.app_settings import AppSettings
from w8s_astro_mcp.models.house_system import HouseSystem, HOUSE_SYSTEM_SEED_DATA
from w8s_astro_mcp.models.location import Location
from w8s_astro_mcp.models.profile import Profile
from w8s_astro_mcp.models.natal_planet import NatalPlanet
from w8s_astro_mcp.models.natal_house import NatalHouse
from w8s_astro_mcp.models.natal_point import NatalPoint
from w8s_astro_mcp.models.transit_lookup import TransitLookup
from w8s_astro_mcp.models.transit_planet import TransitPlanet
from w8s_astro_mcp.models.transit_house import TransitHouse
from w8s_astro_mcp.models.transit_point import TransitPoint
from w8s_astro_mcp.models.connection import Connection
from w8s_astro_mcp.models.connection_member import ConnectionMember
from w8s_astro_mcp.models.connection_chart import ConnectionChart
from w8s_astro_mcp.models.connection_planet import ConnectionPlanet
from w8s_astro_mcp.models.connection_house import ConnectionHouse
from w8s_astro_mcp.models.connection_point import ConnectionPoint
from w8s_astro_mcp.models.event import Event
from w8s_astro_mcp.models.event_planet import EventPlanet
from w8s_astro_mcp.models.event_house import EventHouse
from w8s_astro_mcp.models.event_point import EventPoint

__all__ = [
    "AppSettings",
    "HouseSystem",
    "HOUSE_SYSTEM_SEED_DATA",
    "Location",
    "Profile",
    "NatalPlanet",
    "NatalHouse",
    "NatalPoint",
    "TransitLookup",
    "TransitPlanet",
    "TransitHouse",
    "TransitPoint",
    "Connection",
    "ConnectionMember",
    "ConnectionChart",
    "ConnectionPlanet",
    "ConnectionHouse",
    "ConnectionPoint",
    "Event",
    "EventPlanet",
    "EventHouse",
    "EventPoint",
]
