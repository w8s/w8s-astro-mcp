"""Profile model - identity and birth data for people whose charts we track.

A Profile represents a person's birth information and serves as the root entity
for all astrological data (natal chart, transit lookups, etc.).

Design decisions:
- Only one profile can have is_primary=True (the user's own chart)
- birth_location_id is required (cannot calculate chart without location)
- preferred_house_system_id defaults to Placidus
- Birth data is immutable once set (changing it would invalidate natal chart)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class Profile(Base):
    """
    Person's identity and birth data for astrological calculations.
    
    Each profile can have:
    - One natal chart (calculated from birth data)
    - Many transit lookups (history of transit checks)
    - Many saved locations (home, office, travel spots)
    """
    
    __tablename__ = "profiles"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Profile identification
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    
    # Birth data (immutable)
    birth_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    birth_time: Mapped[str] = mapped_column(String(5), nullable=False)   # HH:MM
    
    # Birth location (FK to locations table)
    birth_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # Is this the user's own chart?
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # Preferred house system for calculations
    preferred_house_system_id: Mapped[int] = mapped_column(
        ForeignKey("house_systems.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
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
    
    # Indexes
    __table_args__ = (
        Index('ix_profiles_name_primary', 'name', 'is_primary'),
    )
    
    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, name='{self.name}', birth_date='{self.birth_date}')>"
    
    def to_dict(self) -> dict:
        """
        Convert profile to dictionary for API responses.
        
        Note: Does not include related objects (birth_location, house_system).
        Use with eager loading if you need those.
        """
        return {
            "id": self.id,
            "name": self.name,
            "birth_date": self.birth_date,
            "birth_time": self.birth_time,
            "birth_location_id": self.birth_location_id,
            "is_primary": self.is_primary,
            "preferred_house_system_id": self.preferred_house_system_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
