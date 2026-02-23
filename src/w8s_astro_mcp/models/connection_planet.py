"""ConnectionPlanet model - planetary positions in a connection chart.

Mirrors natal_planets exactly, but keyed to connection_chart_id instead of profile_id.
One row per planet per connection chart (composite or Davison).

Design decisions:
- Identical field structure to NatalPlanet for consistency and queryability
- FK to connection_charts (not connections directly) — planet data belongs to a
  specific chart type, not the connection as a whole
- ON DELETE CASCADE — removing a chart removes its planet rows
- UNIQUE (connection_chart_id, planet) — one row per planet per chart
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class ConnectionPlanet(Base):
    """
    Planetary position in a composite or Davison chart.

    Structure is identical to NatalPlanet — same fields, same precision,
    same calculation metadata. Only the parent FK differs.
    """

    __tablename__ = "connection_planets"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # The connection chart this belongs to
    connection_chart_id: Mapped[int] = mapped_column(
        ForeignKey("connection_charts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Planet identification
    planet: Mapped[str] = mapped_column(String(20), nullable=False)

    # Position within sign (0-29.999°)
    degree: Mapped[int] = mapped_column(Integer, nullable=False)   # 0-29
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-59
    seconds: Mapped[float] = mapped_column(Float, nullable=False)  # 0-59.999

    # Zodiac sign
    sign: Mapped[str] = mapped_column(String(20), nullable=False)

    # Absolute position (0-359.999°) for aspect calculations
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # Which house (1-12) — may be null if house system not yet calculated
    house_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Retrograde status (composite: averaged; Davison: calculated normally)
    is_retrograde: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    calculation_method: Mapped[str] = mapped_column(String(50), default="pysweph", nullable=False)
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint('connection_chart_id', 'planet', name='uq_connection_planet_chart_planet'),
        Index('ix_connection_planet_chart_sign', 'connection_chart_id', 'sign'),
        Index('ix_connection_planet_absolute_position', 'absolute_position'),
    )

    def __repr__(self) -> str:
        return (
            f"<ConnectionPlanet(id={self.id}, connection_chart_id={self.connection_chart_id}, "
            f"planet='{self.planet}', position={self.degree}°{self.sign})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "connection_chart_id": self.connection_chart_id,
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
        """Human-readable position string (e.g., '15°24'36\" Taurus')."""
        return f"{self.degree}°{self.minutes}'{int(self.seconds)}\" {self.sign}"
