"""Database helper functions for server.py

Provides high-level database operations for the MCP server.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from w8s_astro_mcp.database import get_database_path, create_db_engine, get_session
from w8s_astro_mcp.models import (
    Profile, Location, HouseSystem,
    NatalPlanet, NatalHouse, NatalPoint,
    TransitLookup, TransitPlanet, TransitHouse, TransitPoint
)


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
    
    def get_primary_profile(self) -> Optional[Profile]:
        """Get the primary profile (user's own chart)."""
        with get_session(self.engine) as session:
            return session.query(Profile).filter_by(is_primary=True).first()
    
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
        """
        with get_session(self.engine) as session:
            # Create transit lookup with location snapshot
            lookup = TransitLookup(
                profile_id=profile.id,
                location_id=location.id,
                location_snapshot_label=location.label,
                location_snapshot_latitude=location.latitude,
                location_snapshot_longitude=location.longitude,
                location_snapshot_timezone=location.timezone,
                lookup_datetime=lookup_datetime,
                house_system_id=house_system_id,
                calculation_method='swetest',
                ephemeris_version='2.10.03'  # TODO: Get this from swetest
            )
            session.add(lookup)
            session.flush()
            
            # TODO: Add transit planets, houses, points
            # This requires parsing the transit_data dict and creating rows
            # Similar to migration script logic
            
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
