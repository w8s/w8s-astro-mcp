"""ConnectionChart model - one cached chart per chart type per connection.

Stores the calculated midpoint data (Davison-specific fields) and validity flag.
Actual planet/house/point positions live in connection_planets/houses/points.

Design decisions:
- UNIQUE (connection_id, chart_type) — one composite and one Davison per connection
- is_valid flag for cache invalidation (set False when member birth data changes)
- Davison fields (date, time, lat, lng, timezone) stored here — they ARE the chart
  definition, not just metadata. The Davison chart IS cast for this moment/location.
- ON DELETE CASCADE — removing a connection removes its charts (and child rows cascade)
- chart_type is constrained to 'composite' or 'davison' at application layer
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class ConnectionChart(Base):
    """
    Cached chart for a connection — one row per chart type (composite or Davison).

    is_valid=False signals that cached planet/house/point data is stale and
    must be recalculated before use. Recalculation sets is_valid back to True.
    """

    __tablename__ = "connection_charts"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # The connection this chart belongs to
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Chart type: 'composite' or 'davison'
    chart_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- Davison-specific fields ---
    # These are the calculated midpoint moment and location used to cast the chart.
    # Null for composite charts.
    davison_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)       # YYYY-MM-DD
    davison_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)        # HH:MM
    davison_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    davison_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    davison_timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Cache validity flag — set False when any member's birth data changes
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Calculation metadata
    calculated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    calculation_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Constraints
    __table_args__ = (
        # One composite and one Davison chart per connection
        UniqueConstraint('connection_id', 'chart_type', name='uq_connection_chart_type'),
    )

    def __repr__(self) -> str:
        return (
            f"<ConnectionChart(id={self.id}, connection_id={self.connection_id}, "
            f"chart_type='{self.chart_type}', is_valid={self.is_valid})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "chart_type": self.chart_type,
            "davison_date": self.davison_date,
            "davison_time": self.davison_time,
            "davison_latitude": self.davison_latitude,
            "davison_longitude": self.davison_longitude,
            "davison_timezone": self.davison_timezone,
            "is_valid": self.is_valid,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
            "calculation_method": self.calculation_method,
            "ephemeris_version": self.ephemeris_version,
        }
