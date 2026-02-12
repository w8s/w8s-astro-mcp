"""Database helper functions for server.py

Provides high-level database operations for the MCP server.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from ..database import get_database_path, create_db_engine, get_session
from ..models import (
    AppSettings, Profile, Location, HouseSystem,
    NatalPlanet, NatalHouse, NatalPoint,
    TransitLookup, TransitPlanet, TransitHouse, TransitPoint
)
from .transit_logger import save_transit_data_to_db


class DatabaseHelper:
    """Helper class for database operations."""
    
    def __init__(self):
        """Initialize database helper."""
        db_path = get_database_path()
        if not db_path.exists():
            raise FileNotFoundError(
                f"Database not found at {db_path}. "
                "Run migration script first: python scripts/migrate_config_to_sqlite.py"
            )
        self.engine = create_db_engine(db_path)
    
    def get_current_profile(self) -> Optional[Profile]:
        """
        Get the current user's profile (from AppSettings).
        
        Returns None if no profile is set as current.
        """
        with get_session(self.engine) as session:
            settings = session.query(AppSettings).filter_by(id=1).first()
            if not settings or not settings.current_profile_id:
                return None
            return session.query(Profile).filter_by(id=settings.current_profile_id).first()
    
    def set_current_profile(self, profile_id: int) -> bool:
        """
        Set the current user's profile.
        
        Returns True if successful, False if profile doesn't exist.
        """
        with get_session(self.engine) as session:
            # Verify profile exists
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if not profile:
                return False
            
            # Update or create settings
            settings = session.query(AppSettings).filter_by(id=1).first()
            if not settings:
                settings = AppSettings(id=1, current_profile_id=profile_id)
                session.add(settings)
            else:
                settings.current_profile_id = profile_id
            
            session.commit()
            return True
    
    def get_profile_by_id(self, profile_id: int) -> Optional[Profile]:
        """Get profile by ID."""
        with get_session(self.engine) as session:
            return session.query(Profile).filter_by(id=profile_id).first()
    
    def get_birth_location(self, profile: Profile) -> Optional[Location]:
        """Get birth location for a profile."""
        with get_session(self.engine) as session:
            return session.query(Location).filter_by(id=profile.birth_location_id).first()
    
    def get_current_home_location(self, profile: Profile) -> Optional[Location]:
        """Get current home location for a profile."""
        with get_session(self.engine) as session:
            return session.query(Location).filter(
                Location.profile_id == profile.id,
                Location.is_current_home == True
            ).first()
    
    def get_location_by_label(self, label: str, profile: Profile = None) -> Optional[Location]:
        """Get location by label (case-insensitive)."""
        with get_session(self.engine) as session:
            query = session.query(Location).filter(
                Location.label.ilike(label)
            )
            if profile:
                # Try profile-specific first, then global
                loc = query.filter_by(profile_id=profile.id).first()
                if not loc:
                    loc = query.filter_by(profile_id=None).first()
                return loc
            return query.first()
    
    def get_natal_chart_data(self, profile: Profile) -> Dict[str, Any]:
        """
        Get natal chart data for a profile in the format expected by tools.
        
        Returns dict with 'planets', 'houses', 'points', 'metadata' keys.
        """
        with get_session(self.engine) as session:
            # Get planets
            planets_query = session.query(NatalPlanet).filter_by(profile_id=profile.id).all()
            planets = {}
            for p in planets_query:
                planets[p.planet] = {
                    'sign': p.sign,
                    'degree': p.absolute_position % 30,  # Degree within sign
                    'formatted': p.formatted_position,
                }
            
            # Get houses
            houses_query = session.query(NatalHouse).filter_by(
                profile_id=profile.id,
                house_system_id=profile.preferred_house_system_id
            ).all()
            houses = {}
            for h in houses_query:
                houses[str(h.house_number)] = {
                    'sign': h.sign,
                    'degree': h.absolute_position % 30,
                    'formatted': h.formatted_position,
                }
            
            # Get points
            points_query = session.query(NatalPoint).filter_by(
                profile_id=profile.id,
                house_system_id=profile.preferred_house_system_id
            ).all()
            points = {}
            for pt in points_query:
                points[pt.point_type] = {
                    'sign': pt.sign,
                    'degree': pt.absolute_position % 30,
                    'formatted': pt.formatted_position,
                }
            
            # Get birth location
            birth_loc = session.query(Location).filter_by(id=profile.birth_location_id).first()
            
            # Get house system
            house_system = session.query(HouseSystem).filter_by(
                id=profile.preferred_house_system_id
            ).first()
            
            return {
                'planets': planets,
                'houses': houses,
                'points': points,
                'metadata': {
                    'date': profile.birth_date,
                    'time': profile.birth_time,
                    'latitude': birth_loc.latitude if birth_loc else None,
                    'longitude': birth_loc.longitude if birth_loc else None,
                    'house_system': house_system.name if house_system else 'Placidus'
                }
            }
    
    def save_transit_lookup(
        self,
        profile: Profile,
        location: Location,
        lookup_datetime: datetime,
        transit_data: Dict[str, Any],
        house_system_id: int
    ) -> TransitLookup:
        """
        Save a transit lookup and all its associated data.
        
        Creates rows in:
        - transit_lookups
        - transit_planets (for each planet)
        - transit_houses (for each house)
        - transit_points (for each point)
        
        Args:
            profile: Profile this lookup is for
            location: Location where transits were calculated
            lookup_datetime: When the transits are being analyzed
            transit_data: Parsed swetest output
            house_system_id: House system used
            
        Returns:
            Created TransitLookup object
        """
        with get_session(self.engine) as session:
            lookup = save_transit_data_to_db(
                session,
                profile,
                location,
                lookup_datetime,
                transit_data,
                house_system_id
            )
            session.commit()
            return lookup
    
    def get_house_system_by_code(self, code: str) -> Optional[HouseSystem]:
        """Get house system by code (e.g., 'P' for Placidus)."""
        with get_session(self.engine) as session:
            return session.query(HouseSystem).filter_by(code=code).first()
    
    def get_house_system_by_name(self, name: str) -> Optional[HouseSystem]:
        """Get house system by name (case-insensitive)."""
        with get_session(self.engine) as session:
            return session.query(HouseSystem).filter(
                HouseSystem.name.ilike(name)
            ).first()
    
    def list_all_profiles(self) -> List[Profile]:
        """List all profiles."""
        with get_session(self.engine) as session:
            return session.query(Profile).all()
    
    def list_all_locations(self, profile: Profile = None) -> List[Location]:
        """List all locations (optionally filtered by profile)."""
        with get_session(self.engine) as session:
            if profile:
                # Profile-specific and global locations
                return session.query(Location).filter(
                    (Location.profile_id == profile.id) | (Location.profile_id == None)
                ).all()
            return session.query(Location).all()
    
    def create_profile_with_location(
        self,
        name: str,
        birth_date: str,
        birth_time: str,
        birth_location_name: str,
        birth_latitude: float,
        birth_longitude: float,
        birth_timezone: str,
        preferred_house_system_id: int = 1  # Default to Placidus
    ) -> Profile:
        """
        Create a new profile with its birth location.
        
        This is atomic - either both profile and location are created, or neither.
        
        Args:
            name: Person's name
            birth_date: YYYY-MM-DD format
            birth_time: HH:MM format (24-hour)
            birth_location_name: Display name for location
            birth_latitude: Latitude in decimal degrees
            birth_longitude: Longitude in decimal degrees
            birth_timezone: Timezone (e.g., 'America/Chicago')
            preferred_house_system_id: House system ID (default: 1 = Placidus)
            
        Returns:
            Created Profile object with birth_location_id set
        """
        with get_session(self.engine) as session:
            # Create birth location first (will get profile_id after profile creation)
            birth_location = Location(
                profile_id=None,  # Temporary - will update after profile creation
                label="Birth",
                latitude=birth_latitude,
                longitude=birth_longitude,
                timezone=birth_timezone,
                is_current_home=True,  # Birth location starts as home
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(birth_location)
            session.flush()  # Get the location ID
            
            # Create profile
            profile = Profile(
                name=name,
                birth_date=birth_date,
                birth_time=birth_time,
                birth_location_id=birth_location.id,
                preferred_house_system_id=preferred_house_system_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(profile)
            session.flush()  # Get the profile ID
            
            # Update location with profile_id
            birth_location.profile_id = profile.id
            
            session.commit()
            return profile
    
    def create_location(
        self,
        profile_id: int,
        label: str,
        latitude: float,
        longitude: float,
        timezone: str,
        set_as_home: bool = False
    ) -> Location:
        """
        Create a new location for a profile.
        
        Args:
            profile_id: Profile this location belongs to
            label: Display name (e.g., "Home", "Office", "Paris Trip")
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            timezone: Timezone (e.g., 'America/Chicago')
            set_as_home: If True, unsets is_current_home on other locations
            
        Returns:
            Created Location object
            
        Raises:
            ValueError: If profile doesn't exist
        """
        with get_session(self.engine) as session:
            # Verify profile exists
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")
            
            # If set_as_home, unset all other current_home flags for this profile
            if set_as_home:
                session.query(Location).filter_by(
                    profile_id=profile_id,
                    is_current_home=True
                ).update({"is_current_home": False})
            
            # Create location
            location = Location(
                profile_id=profile_id,
                label=label,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                is_current_home=set_as_home,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(location)
            session.commit()
            return location
