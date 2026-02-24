"""Event model - a chart cast for a moment in time and place.

No profile or person required. Useful for weddings, business launches,
historical events, and electional astrology.

Design decisions:
- label is nullable — ad-hoc charts are calculated and returned without saving
- profile_id is nullable — events can optionally be associated with a person
- location stored as snapshot fields (like transit_lookups) — no FK to locations
- immutable once saved — delete and re-cast if details change
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class Event(Base):
    """
    A chart cast for a specific moment in time and place.

    Saved events (with a label) are queryable and comparable via compare_charts.
    Ad-hoc events (no label) are calculated, returned, and not persisted.
    """

    __tablename__ = "events"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # User-defined name — unique, nullable (None = ad-hoc, not saved)
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)

    # The moment being charted
    event_date: Mapped[str] = mapped_column(String(10), nullable=False)   # YYYY-MM-DD
    event_time: Mapped[str] = mapped_column(String(5), nullable=False)    # HH:MM

    # Location snapshot — not a FK, matches transit_lookups pattern
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)     # IANA
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Optional notes
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Optional profile association (SET NULL on profile delete)
    profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # House system used for this chart
    house_system_id: Mapped[int] = mapped_column(
        ForeignKey("house_systems.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Calculation metadata
    calculation_method: Mapped[str] = mapped_column(String(50), default="pysweph", nullable=False)
    ephemeris_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_events_event_date", "event_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event(id={self.id}, label='{self.label}', "
            f"date={self.event_date} {self.event_time}, location='{self.location_name}')>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "label": self.label,
            "event_date": self.event_date,
            "event_time": self.event_time,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "location_name": self.location_name,
            "description": self.description,
            "profile_id": self.profile_id,
            "house_system_id": self.house_system_id,
            "calculation_method": self.calculation_method,
            "ephemeris_version": self.ephemeris_version,
            "created_at": self.created_at.isoformat(),
        }
