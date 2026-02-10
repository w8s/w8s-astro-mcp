"""NatalPoint model - special points in the natal chart.

Stores positions of astrological points that aren't planets:
- Ascendant (ASC)
- Midheaven (MC)
- North Node
- South Node
- Vertex (optional)
- Part of Fortune (optional)

Design decisions:
- point_type identifies which point (ASC, MC, etc.)
- Same structure as NatalPlanet (degree/minutes/seconds)
- Unique constraint on (profile_id, house_system_id, point_type)
- house_system_id because ASC/MC depend on house system
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class NatalPoint(Base):
    """
    Special astrological points in the natal chart.
    
    Includes angles (ASC, MC) and nodes which are calculated separately
    from planetary positions.
    """
    
    __tablename__ = "natal_points"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Profile this belongs to
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
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
        default="swetest",
        nullable=False
    )
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Constraints
    __table_args__ = (
        # One row per point type per profile per house system
        UniqueConstraint(
            'profile_id', 'house_system_id', 'point_type',
            name='uq_natal_point_profile_system_type'
        ),
        # Index for point type queries
        Index('ix_natal_point_profile_type', 'profile_id', 'point_type'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<NatalPoint(id={self.id}, profile_id={self.profile_id}, "
            f"point='{self.point_type}', position={self.degree}°{self.sign})>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "profile_id": self.profile_id,
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
