"""ConnectionHouse model - house cusps in a connection chart.

Mirrors natal_houses exactly, but keyed to connection_chart_id instead of profile_id.
One row per house (1-12) per connection chart per house system.

Design decisions:
- Identical field structure to NatalHouse for consistency
- house_system_id retained — composite/Davison charts support the same house systems
- UNIQUE (connection_chart_id, house_number) — one cusp per house per chart
  (simplified vs natal which also keys on house_system_id, since a connection chart
  is always calculated with one house system; that system is implicit in the chart)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class ConnectionHouse(Base):
    """
    House cusp position in a composite or Davison chart.

    Structure mirrors NatalHouse — same fields, same precision,
    same calculation metadata.
    """

    __tablename__ = "connection_houses"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # The connection chart this belongs to
    connection_chart_id: Mapped[int] = mapped_column(
        ForeignKey("connection_charts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # House system used for this calculation
    house_system_id: Mapped[int] = mapped_column(
        ForeignKey("house_systems.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # House number (1-12)
    house_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Position within sign (0-29.999°)
    degree: Mapped[int] = mapped_column(Integer, nullable=False)   # 0-29
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-59
    seconds: Mapped[float] = mapped_column(Float, nullable=False)  # 0-59.999

    # Zodiac sign
    sign: Mapped[str] = mapped_column(String(20), nullable=False)

    # Absolute position (0-359.999°) for calculations
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    calculation_method: Mapped[str] = mapped_column(String(50), default="swetest", nullable=False)
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'connection_chart_id', 'house_number',
            name='uq_connection_house_chart_number'
        ),
        Index('ix_connection_house_chart_sign', 'connection_chart_id', 'sign'),
    )

    def __repr__(self) -> str:
        return (
            f"<ConnectionHouse(id={self.id}, connection_chart_id={self.connection_chart_id}, "
            f"house={self.house_number}, position={self.degree}°{self.sign})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "connection_chart_id": self.connection_chart_id,
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
        """Human-readable position string (e.g., '15°24'36\" Taurus')."""
        return f"{self.degree}°{self.minutes}'{int(self.seconds)}\" {self.sign}"
