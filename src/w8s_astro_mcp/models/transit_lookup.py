"""TransitLookup model - history of transit calculations.

Records when we checked transits for a profile at a specific location.
Each lookup spawns rows in transit_planets, transit_houses, transit_points.

Design decisions:
- location_id FK for WHERE the transits were calculated
- Denormalized location snapshot for historical accuracy
- lookup_datetime is the moment we're analyzing (not when we ran the calculation)
- Unique constraint prevents duplicate lookups
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class TransitLookup(Base):
    """
    Record of a transit calculation for a profile.
    
    Each row represents one "check transits at this location and time" request.
    The actual transit data lives in transit_planets/houses/points tables.
    """
    
    __tablename__ = "transit_lookups"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Profile this belongs to
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Location where transits were calculated
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # Denormalized location snapshot (for historical accuracy)
    # If location details change later, we preserve what they were
    location_snapshot_label: Mapped[str] = mapped_column(String(200), nullable=False)
    location_snapshot_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_snapshot_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_snapshot_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # When are we analyzing? (e.g., "2026-02-09 12:00")
    lookup_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # House system used for this lookup
    house_system_id: Mapped[int] = mapped_column(
        ForeignKey("house_systems.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    calculation_method: Mapped[str] = mapped_column(
        String(50),
        default="pysweph",
        nullable=False
    )
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Constraints
    __table_args__ = (
        # Prevent duplicate lookups
        UniqueConstraint(
            'profile_id', 'lookup_datetime', 'location_id', 'house_system_id',
            name='uq_transit_lookup_profile_time_location_system'
        ),
        # Index for recent lookups
        Index('ix_transit_lookup_profile_datetime', 'profile_id', 'lookup_datetime'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TransitLookup(id={self.id}, profile_id={self.profile_id}, "
            f"datetime='{self.lookup_datetime}', location='{self.location_snapshot_label}')>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "location_id": self.location_id,
            "location_snapshot": {
                "label": self.location_snapshot_label,
                "latitude": self.location_snapshot_latitude,
                "longitude": self.location_snapshot_longitude,
                "timezone": self.location_snapshot_timezone,
            },
            "lookup_datetime": self.lookup_datetime.isoformat(),
            "house_system_id": self.house_system_id,
            "calculated_at": self.calculated_at.isoformat(),
            "calculation_method": self.calculation_method,
            "ephemeris_version": self.ephemeris_version,
        }
