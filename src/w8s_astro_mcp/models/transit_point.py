"""TransitPoint model - special points at a specific transit lookup.

Stores positions of astrological points at the moment of a transit lookup:
- Ascendant (ASC)
- Midheaven (MC)
- North Node
- South Node
- Vertex (optional)
- Part of Fortune (optional)

Design decisions:
- transit_lookup_id FK instead of profile_id
- house_system_id from TransitLookup but duplicated for safety
- Same structure as NatalPoint (degree/minutes/seconds/sign/absolute_position)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class TransitPoint(Base):
    """
    Special astrological point at a specific transit lookup.
    
    Each row represents where one point was positioned at the lookup time.
    """
    
    __tablename__ = "transit_points"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Transit lookup this belongs to
    transit_lookup_id: Mapped[int] = mapped_column(
        ForeignKey("transit_lookups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # House system (ASC/MC depend on this, nodes don't)
    house_system_id: Mapped[int] = mapped_column(
        ForeignKey("house_systems.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # Point type
    point_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )  # ASC, MC, North Node, South Node, Vertex, Part of Fortune
    
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
        # One row per point type per transit lookup
        UniqueConstraint('transit_lookup_id', 'point_type', name='uq_transit_point_lookup_type'),
        # Index for point type queries
        Index('ix_transit_point_lookup_type', 'transit_lookup_id', 'point_type'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TransitPoint(id={self.id}, lookup_id={self.transit_lookup_id}, "
            f"point='{self.point_type}', position={self.degree}°{self.sign})>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "transit_lookup_id": self.transit_lookup_id,
            "house_system_id": self.house_system_id,
            "point_type": self.point_type,
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
