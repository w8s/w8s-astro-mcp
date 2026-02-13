"""Location model - reusable location data for birth places and transit lookups.

Every location belongs to a profile. Common use cases:
- Birth location (linked via Profile.birth_location_id)
- Current home (is_current_home=True)
- Saved places (office, travel destinations, etc.)

Examples:
- "Birth" (used as birth_location_id)
- "Home" (is_current_home=True)
- "Office" 
- "Paris Trip 2025"
"""

from datetime import datetime, timezone

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class Location(Base):
    """
    Reusable location data for astrological calculations.
    
    Design decisions:
    - Every location belongs to a profile (profile_id required)
    - Only one location per profile can have is_current_home=True
    - Unique constraint on (profile_id, label) prevents duplicate names per profile
    - Reserved labels: "current" (uses is_current_home), "birth" (uses profile.birth_location_id)
    - Deleting profile CASCADE deletes all its locations
    """
    
    __tablename__ = "locations"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Profile ownership (nullable during creation for chicken-and-egg scenario)
    # Note: In practice, every location should have a profile_id after creation
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=True,  # Temporarily null during atomic profile+location creation
        index=True
    )
    
    # User-friendly label
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Geographic coordinates
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    
    # IANA timezone (e.g., "America/Chicago")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Is this the default location for this profile's transits?
    is_current_home: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Constraints
    __table_args__ = (
        # Unique label per profile
        UniqueConstraint('profile_id', 'label', name='uq_location_profile_label'),
        # Index for finding current home
        Index('ix_location_profile_current', 'profile_id', 'is_current_home'),
    )
    
    def __repr__(self) -> str:
        return f"<Location(id={self.id}, label='{self.label}', lat={self.latitude}, lng={self.longitude})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "label": self.label,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "is_current_home": self.is_current_home,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
