"""TransitLookup model for tracking transit calculation history.

Stores a history of all transit calculations performed, including:
- Which profile the transit was for
- When the transit was calculated (lookup time)
- The date/time of the transit itself
- Location where the transit was calculated
- The full transit data
- Optional user notes
"""

from datetime import datetime, timezone
from typing import Optional
import json

from sqlalchemy import String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from w8s_astro_mcp.database import Base


class TransitLookup(Base):
    """
    Record of a transit calculation.
    
    This allows users to:
    - Review their transit lookup history
    - See when they checked specific transits
    - Track patterns in what transits they're interested in
    - Export transit history for journaling
    """
    
    __tablename__ = "transit_lookups"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Foreign key to profile
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Transit date/time (the date being looked up)
    transit_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    transit_time: Mapped[str] = mapped_column(String(5), nullable=False)   # HH:MM
    
    # Location where transit was calculated (can differ from birth location)
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Transit data (JSON blob)
    # Structure: {"planets": {...}, "houses": {...}, "points": {...}, "metadata": {...}}
    transit_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional user notes about this transit
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # When this lookup was performed
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # Relationship to profile
    # Using string reference to avoid circular imports
    profile: Mapped["Profile"] = relationship(
        "Profile",
        backref="transit_lookups",
        lazy="joined"
    )
    
    # Indexes for common queries
    __table_args__ = (
        # Find all transits for a profile
        Index('ix_transit_lookups_profile_date', 'profile_id', 'transit_date'),
        # Find recent lookups
        Index('ix_transit_lookups_created', 'created_at'),
        # Find lookups by transit date
        Index('ix_transit_lookups_transit_date', 'transit_date'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TransitLookup(id={self.id}, profile_id={self.profile_id}, "
            f"transit_date='{self.transit_date}', created_at='{self.created_at}')>"
        )
    
    def get_transit_data(self) -> dict:
        """
        Get the transit data as a dictionary.
        
        Returns:
            Transit data dict
        """
        return json.loads(self.transit_data_json)
    
    def set_transit_data(self, transit_data: dict) -> None:
        """
        Set the transit data.
        
        Args:
            transit_data: Dictionary with planets, houses, points, metadata
        """
        self.transit_data_json = json.dumps(transit_data)
    
    def to_dict(self) -> dict:
        """
        Convert transit lookup to dictionary for API responses.
        
        Returns:
            Dictionary representation of the transit lookup
        """
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "profile_name": self.profile.name if self.profile else None,
            "transit_date": self.transit_date,
            "transit_time": self.transit_time,
            "location": {
                "name": self.location_name,
                "latitude": self.location_latitude,
                "longitude": self.location_longitude,
                "timezone": self.location_timezone,
            },
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
