"""TransitHouse model - house cusps at a specific transit lookup.

Stores house cusp positions at the moment of a transit lookup.
One row per house (1-12) per transit lookup.

Design decisions:
- transit_lookup_id FK instead of profile_id
- house_system_id from TransitLookup but duplicated for safety
- Same structure as NatalHouse (degree/minutes/seconds/sign/absolute_position)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class TransitHouse(Base):
    """
    House cusp position at a specific transit lookup.
    
    Each row represents where one house cusp was positioned at the lookup time.
    """
    
    __tablename__ = "transit_houses"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Transit lookup this belongs to
    transit_lookup_id: Mapped[int] = mapped_column(
        ForeignKey("transit_lookups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # House system used
    house_system_id: Mapped[int] = mapped_column(
        ForeignKey("house_systems.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # House number (1-12)
    house_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Position within sign (0-29.999°)
    degree: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-29
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-59
    seconds: Mapped[float] = mapped_column(Float, nullable=False)  # 0-59.999
    
    # Zodiac sign
    sign: Mapped[str] = mapped_column(String(20), nullable=False)  # Aries, Taurus, etc.
    
    # Absolute position (0-359.999°) for calculations
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    
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
        # One row per house per transit lookup
        UniqueConstraint('transit_lookup_id', 'house_number', name='uq_transit_house_lookup_number'),
        # Index for sign-based queries
        Index('ix_transit_house_lookup_sign', 'transit_lookup_id', 'sign'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TransitHouse(id={self.id}, lookup_id={self.transit_lookup_id}, "
            f"house={self.house_number}, position={self.degree}°{self.sign})>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "transit_lookup_id": self.transit_lookup_id,
            "house_system_id": self.house_system_id,
            "house_number": self.house_number,
            "degree": self.degree,
            "minutes": self.minutes,
            "seconds": self.seconds,
            "sign": self.sign,
            "absolute_position": self.absolute_position,
            "calculated_at": self.calculated_at.isoformat(),
            "calculation_method": self.calculation_method,
            "ephemeris_version": self.ephemeris_version,
        }
    
    @property
    def formatted_position(self) -> str:
        """Human-readable position string (e.g., '15°24'36" Taurus')."""
        return f"{self.degree}°{self.minutes}'{int(self.seconds)}\" {self.sign}"
