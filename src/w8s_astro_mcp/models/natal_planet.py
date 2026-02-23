"""NatalPlanet model - planetary positions in the natal chart.

Stores the position of each planet at the moment of birth.
One row per planet per profile.

Design decisions:
- degree/minutes/seconds for human-readable precision
- absolute_position (0-360°) for calculations and aspect detection
- house_number links planet to natal house
- Calculation metadata for reproducibility
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class NatalPlanet(Base):
    """
    Planetary position in the natal chart.
    
    Each row represents where one planet was positioned at birth.
    """
    
    __tablename__ = "natal_planets"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Profile this belongs to
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
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
    
    # Which house (1-12)
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
        default="pysweph",
        nullable=False
    )
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Constraints
    __table_args__ = (
        # One row per planet per profile
        UniqueConstraint('profile_id', 'planet', name='uq_natal_planet_profile_planet'),
        # Index for sign-based queries
        Index('ix_natal_planet_profile_sign', 'profile_id', 'sign'),
        # Index for aspect calculations
        Index('ix_natal_planet_absolute_position', 'absolute_position'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<NatalPlanet(id={self.id}, profile_id={self.profile_id}, "
            f"planet='{self.planet}', position={self.degree}°{self.sign})>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "profile_id": self.profile_id,
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
