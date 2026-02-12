"""TransitPlanet model - planetary positions at a specific transit lookup.

Stores where planets were positioned at the moment of a transit lookup.
One row per planet per transit lookup.

Design decisions:
- transit_lookup_id FK instead of profile_id
- house_number = which NATAL house the transiting planet is in
- Same structure as NatalPlanet (degree/minutes/seconds/sign/absolute_position)
- Calculation metadata inherited from TransitLookup but duplicated for safety
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class TransitPlanet(Base):
    """
    Planetary position at a specific transit lookup.
    
    Each row represents where one planet was positioned at the lookup time.
    """
    
    __tablename__ = "transit_planets"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Transit lookup this belongs to
    transit_lookup_id: Mapped[int] = mapped_column(
        ForeignKey("transit_lookups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Planet identification
    planet: Mapped[str] = mapped_column(String(20), nullable=False)  # Sun, Moon, Mercury, etc.
    
    # Position within sign (0-29.999°)
    degree: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-29
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-59
    seconds: Mapped[float] = mapped_column(Float, nullable=False)  # 0-59.999
    
    # Zodiac sign
    sign: Mapped[str] = mapped_column(String(20), nullable=False)  # Aries, Taurus, etc.
    
    # Absolute position (0-359.999°) for calculations
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    
    # Which NATAL house is this transiting planet in? (1-12)
    house_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Retrograde status
    is_retrograde: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    calculation_method: Mapped[str] = mapped_column(
        String(50),
        default="swetest",
        nullable=False
    )
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Constraints
    __table_args__ = (
        # One row per planet per transit lookup
        UniqueConstraint('transit_lookup_id', 'planet', name='uq_transit_planet_lookup_planet'),
        # Index for sign-based queries
        Index('ix_transit_planet_lookup_sign', 'transit_lookup_id', 'sign'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TransitPlanet(id={self.id}, lookup_id={self.transit_lookup_id}, "
            f"planet='{self.planet}', position={self.degree}°{self.sign})>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "transit_lookup_id": self.transit_lookup_id,
            "planet": self.planet,
            "degree": self.degree,
            "minutes": self.minutes,
            "seconds": self.seconds,
            "sign": self.sign,
            "absolute_position": self.absolute_position,
            "house_number": self.house_number,
            "is_retrograde": self.is_retrograde,
            "calculated_at": self.calculated_at.isoformat(),
            "calculation_method": self.calculation_method,
            "ephemeris_version": self.ephemeris_version,
        }
    
    @property
    def formatted_position(self) -> str:
        """Human-readable position string (e.g., '15°24'36" Taurus')."""
        return f"{self.degree}°{self.minutes}'{int(self.seconds)}\" {self.sign}"
