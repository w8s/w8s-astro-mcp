"""Database helper functions for server.py

Provides high-level database operations for the MCP server.
"""

from datetime import datetime
from pathlib import Path
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
    
    def __init__(self, db_path: str = None):
        """Initialize database helper.

        Args:
            db_path: Optional path to a SQLite database file.
                     When provided (e.g. in tests), the file is created if it
                     doesn't exist and all tables are initialised automatically.
                     When omitted, uses the standard production path and raises
                     FileNotFoundError if the database hasn't been migrated yet.
        """
        from ..database import create_tables
        if db_path is not None:
            resolved = Path(db_path)
            self.engine = create_db_engine(resolved)
            create_tables(self.engine)
        else:
            resolved = get_database_path()
            if not resolved.exists():
                raise FileNotFoundError(
                    f"Database not found at {resolved}. "
                    "Run migration script first: python scripts/migrate_config_to_sqlite.py"
                )
            self.engine = create_db_engine(resolved)
    
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
        """Get current home location for a profile.
        
        Searches for locations with is_current_home=True that are either:
        - Owned by this profile (profile_id = profile.id)
        - Shared locations (profile_id = NULL)
        """
        with get_session(self.engine) as session:
            return session.query(Location).filter(
                ((Location.profile_id == profile.id) | (Location.profile_id == None)),
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
    
    def update_profile_field(
        self,
        profile_id: int,
        field: str,
        value: str
    ) -> Profile:
        """
        Update a single field on a profile.
        
        Args:
            profile_id: Profile to update
            field: Field name (must be one of: "name", "birth_date", "birth_time")
            value: New value for the field
            
        Returns:
            Updated Profile object
            
        Raises:
            ValueError: If profile doesn't exist or field is invalid
        """
        ALLOWED_FIELDS = ["name", "birth_date", "birth_time"]
        
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Invalid field '{field}'. Must be one of: {', '.join(ALLOWED_FIELDS)}")
        
        with get_session(self.engine) as session:
            # Get profile
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")
            
            # Update field
            setattr(profile, field, value)
            profile.updated_at = datetime.now()
            
            # If birth data changed, invalidate natal cache
            if field in ["birth_date", "birth_time"]:
                self._invalidate_natal_cache(session, profile_id)
            
            session.commit()
            return profile
    
    def _invalidate_natal_cache(self, session, profile_id: int):
        """
        Delete cached natal chart data for a profile.
        
        Called when birth_date or birth_time changes.
        
        Args:
            session: Active database session
            profile_id: Profile whose natal data should be cleared
        """
        # Delete natal planets
        session.query(NatalPlanet).filter_by(profile_id=profile_id).delete()
        
        # Delete natal houses
        session.query(NatalHouse).filter_by(profile_id=profile_id).delete()
        
        # Delete natal points
        session.query(NatalPoint).filter_by(profile_id=profile_id).delete()
        
        # Note: We don't need to commit here - caller will commit
    
    def get_location_by_id(self, location_id: int) -> Optional[Location]:
        """Get location by ID."""
        with get_session(self.engine) as session:
            return session.query(Location).filter_by(id=location_id).first()
    
    def is_location_used_as_birth_location(self, location_id: int) -> Optional[Profile]:
        """
        Check if a location is being used as a birth location.
        
        Args:
            location_id: Location to check
            
        Returns:
            Profile using this location as birth location, or None if not used
        """
        with get_session(self.engine) as session:
            return session.query(Profile).filter_by(birth_location_id=location_id).first()
    
    def delete_location(self, location_id: int) -> bool:
        """
        Delete a location.
        
        Args:
            location_id: Location to delete
            
        Returns:
            True if deleted, False if location doesn't exist
            
        Raises:
            ValueError: If location is being used as a birth location
        """
        with get_session(self.engine) as session:
            # Check if location exists
            location = session.query(Location).filter_by(id=location_id).first()
            if not location:
                return False
            
            # Check if used as birth location
            profile_using = session.query(Profile).filter_by(birth_location_id=location_id).first()
            if profile_using:
                raise ValueError(
                    f"Cannot delete location - it is the birth location for profile '{profile_using.name}' (ID: {profile_using.id})"
                )
            
            # Delete location
            session.delete(location)
            session.commit()
            return True
    
    def delete_profile(self, profile_id: int) -> bool:
        """
        Delete a profile and all associated data.
        
        Database CASCADE will automatically delete:
        - natal_planets (FK: profile_id ON DELETE CASCADE)
        - natal_houses (FK: profile_id ON DELETE CASCADE)
        - natal_points (FK: profile_id ON DELETE CASCADE)
        - locations (FK: profile_id ON DELETE CASCADE)
        - transit_lookups (FK: profile_id ON DELETE CASCADE)
        
        If this profile is the current_profile, AppSettings.current_profile_id
        will be set to NULL automatically (ON DELETE SET NULL).
        
        Args:
            profile_id: Profile to delete
            
        Returns:
            True if deleted, False if profile doesn't exist
        """
        with get_session(self.engine) as session:
            # Check if profile exists
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if not profile:
                return False
            
            # Delete profile - CASCADE handles all related data
            session.delete(profile)
            session.commit()
            return True


    # =========================================================================
    # Phase 7 — Connection Management
    # =========================================================================

    def create_connection(
        self,
        label: str,
        profile_ids: list[int],
        type: str = None,
        start_date: str = None,
    ):
        """Create a connection and add initial members."""
        from ..models import Connection, ConnectionMember
        with get_session(self.engine) as session:
            conn = Connection(label=label, type=type, start_date=start_date)
            session.add(conn)
            session.flush()
            for pid in profile_ids:
                session.add(ConnectionMember(connection_id=conn.id, profile_id=pid))
            session.commit()
            session.refresh(conn)
            return conn

    def list_all_connections(self) -> list:
        """Return all connections."""
        from ..models import Connection
        with get_session(self.engine) as session:
            return session.query(Connection).order_by(Connection.label).all()

    def get_connection_by_id(self, connection_id: int):
        """Return a Connection by ID, or None."""
        from ..models import Connection
        with get_session(self.engine) as session:
            return session.query(Connection).filter_by(id=connection_id).first()

    def get_connection_members(self, connection) -> list:
        """Return Profile objects that are members of this connection."""
        from ..models import ConnectionMember, Profile
        with get_session(self.engine) as session:
            rows = (
                session.query(Profile)
                .join(ConnectionMember, ConnectionMember.profile_id == Profile.id)
                .filter(ConnectionMember.connection_id == connection.id)
                .all()
            )
            return rows

    def add_connection_member(self, connection_id: int, profile_id: int) -> None:
        """Add a profile to a connection (raises IntegrityError on duplicate)."""
        from ..models import ConnectionMember
        with get_session(self.engine) as session:
            session.add(ConnectionMember(connection_id=connection_id, profile_id=profile_id))
            session.commit()

    def remove_connection_member(self, connection_id: int, profile_id: int) -> None:
        """Remove a profile from a connection."""
        from ..models import ConnectionMember
        with get_session(self.engine) as session:
            row = session.query(ConnectionMember).filter_by(
                connection_id=connection_id, profile_id=profile_id
            ).first()
            if row:
                session.delete(row)
                session.commit()

    def delete_connection(self, connection_id: int) -> bool:
        """Delete a connection and all its charts (CASCADE)."""
        from ..models import Connection
        with get_session(self.engine) as session:
            conn = session.query(Connection).filter_by(id=connection_id).first()
            if not conn:
                return False
            session.delete(conn)
            session.commit()
            return True

    def get_connection_chart(self, connection_id: int, chart_type: str):
        """Return cached ConnectionChart or None."""
        from ..models import ConnectionChart
        with get_session(self.engine) as session:
            return session.query(ConnectionChart).filter_by(
                connection_id=connection_id, chart_type=chart_type
            ).first()

    def invalidate_connection_charts(self, connection_id: int) -> None:
        """Mark all charts for a connection as invalid."""
        from ..models import ConnectionChart
        from datetime import timezone
        with get_session(self.engine) as session:
            charts = session.query(ConnectionChart).filter_by(
                connection_id=connection_id
            ).all()
            for chart in charts:
                chart.is_valid = False
            session.commit()

    @staticmethod
    def _normalize_position(data: dict) -> dict:
        """
        Ensure a position dict has degree (int), minutes (int), seconds (float),
        and absolute_position (float).

        Handles two input formats:
          - Composite math output: already has all four keys (degree is int, etc.)
          - Swetest parser output: has 'degree' as decimal-within-sign float,
            'sign' string, no minutes/seconds/absolute_position

        Returns a new dict with all four keys guaranteed.
        """
        from .position_utils import decimal_to_dms, sign_to_absolute_position

        result = dict(data)

        # If absolute_position is missing, derive it from sign + decimal degree
        if "absolute_position" not in result:
            result["absolute_position"] = sign_to_absolute_position(
                result["sign"], result["degree"]
            )

        # If minutes/seconds are missing (swetest format), split decimal degree
        if "minutes" not in result or "seconds" not in result:
            deg_int, min_int, sec_float = decimal_to_dms(result["degree"])
            result["degree"] = deg_int
            result["minutes"] = min_int
            result["seconds"] = sec_float

        return result

    def save_connection_chart(
        self,
        connection_id: int,
        chart_type: str,
        positions: dict,
        davison_midpoint: dict = None,
        calculation_method: str = "swetest",
    ):
        """
        Persist a calculated chart to the DB.

        Upserts the ConnectionChart row, then replaces all planet/house/point rows.
        `positions` must have keys 'planets', 'houses', 'points'.
        Each value is a dict: {name: {absolute_position, sign, degree, minutes, seconds, ...}}
        """
        from datetime import timezone as tz
        from ..models import (
            ConnectionChart, ConnectionPlanet, ConnectionHouse,
            ConnectionPoint, HouseSystem, HOUSE_SYSTEM_SEED_DATA,
        )
        with get_session(self.engine) as session:
            # Upsert chart row
            chart = session.query(ConnectionChart).filter_by(
                connection_id=connection_id, chart_type=chart_type
            ).first()
            if chart is None:
                chart = ConnectionChart(
                    connection_id=connection_id, chart_type=chart_type
                )
                session.add(chart)

            chart.is_valid = True
            chart.calculated_at = datetime.now(tz.utc)
            chart.calculation_method = calculation_method
            chart.ephemeris_version = "2.10"

            if davison_midpoint:
                chart.davison_date = davison_midpoint.get("date")
                chart.davison_time = davison_midpoint.get("time")
                chart.davison_latitude = davison_midpoint.get("latitude")
                chart.davison_longitude = davison_midpoint.get("longitude")
                chart.davison_timezone = davison_midpoint.get("timezone", "UTC")

            session.flush()

            # Get Placidus house system id (default)
            hs = session.query(HouseSystem).filter_by(code="P").first()
            hs_id = hs.id if hs else None

            # Replace planets
            session.query(ConnectionPlanet).filter_by(
                connection_chart_id=chart.id
            ).delete()
            for planet_name, data in positions.get("planets", {}).items():
                d = self._normalize_position(data)
                session.add(ConnectionPlanet(
                    connection_chart_id=chart.id,
                    planet=planet_name,
                    degree=int(d["degree"]),
                    minutes=int(d["minutes"]),
                    seconds=float(d["seconds"]),
                    sign=d.get("sign", ""),
                    absolute_position=d["absolute_position"],
                    is_retrograde=d.get("is_retrograde", False),
                    calculation_method=calculation_method,
                ))

            # Replace houses
            session.query(ConnectionHouse).filter_by(
                connection_chart_id=chart.id
            ).delete()
            for house_key, data in positions.get("houses", {}).items():
                d = self._normalize_position(data)
                session.add(ConnectionHouse(
                    connection_chart_id=chart.id,
                    house_system_id=hs_id,
                    house_number=int(house_key),
                    degree=int(d["degree"]),
                    minutes=int(d["minutes"]),
                    seconds=float(d["seconds"]),
                    sign=d.get("sign", ""),
                    absolute_position=d["absolute_position"],
                    calculation_method=calculation_method,
                ))

            # Replace points
            session.query(ConnectionPoint).filter_by(
                connection_chart_id=chart.id
            ).delete()
            for point_type, data in positions.get("points", {}).items():
                d = self._normalize_position(data)
                session.add(ConnectionPoint(
                    connection_chart_id=chart.id,
                    house_system_id=hs_id,
                    point_type=point_type,
                    degree=int(d["degree"]),
                    minutes=int(d["minutes"]),
                    seconds=float(d["seconds"]),
                    sign=d.get("sign", ""),
                    absolute_position=d["absolute_position"],
                    calculation_method=calculation_method,
                ))

            session.commit()
            session.refresh(chart)
            return chart

    def get_connection_planets(self, connection_chart_id: int) -> list:
        """Return ConnectionPlanet rows for a chart."""
        from ..models import ConnectionPlanet
        with get_session(self.engine) as session:
            return session.query(ConnectionPlanet).filter_by(
                connection_chart_id=connection_chart_id
            ).order_by(ConnectionPlanet.planet).all()

    def get_connection_houses(self, connection_chart_id: int) -> list:
        """Return ConnectionHouse rows for a chart."""
        from ..models import ConnectionHouse
        with get_session(self.engine) as session:
            return session.query(ConnectionHouse).filter_by(
                connection_chart_id=connection_chart_id
            ).order_by(ConnectionHouse.house_number).all()

    def get_connection_points(self, connection_chart_id: int) -> list:
        """Return ConnectionPoint rows for a chart."""
        from ..models import ConnectionPoint
        with get_session(self.engine) as session:
            return session.query(ConnectionPoint).filter_by(
                connection_chart_id=connection_chart_id
            ).order_by(ConnectionPoint.point_type).all()
