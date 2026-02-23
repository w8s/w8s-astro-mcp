"""Connection model - a grouping of 2+ profiles for astrological comparison.

A Connection represents any meaningful relationship between people:
romantic, family, professional, or friendship. It serves as the root
entity for composite and Davison chart calculations.

Design decisions:
- N members supported (not just pairs) — junction table handles any count
- type is optional/freeform (no enum constraint — leave flexibility to user)
- start_date is optional (not all relationships have a clear start date)
- Charts are stored on connection_charts, not here
- Minimum member count (≥2) enforced at application layer, not SQL
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class Connection(Base):
    """
    A named grouping of 2+ profiles for relationship chart analysis.

    Supports composite and Davison chart calculation once members are added.
    Charts are lazily calculated and cached in connection_charts.
    """

    __tablename__ = "connections"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Human-readable label (e.g. "Todd & Sarah", "The Johnson Family")
    label: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # Relationship type — optional, freeform
    # Suggested values: romantic, family, professional, friendship
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Optional relationship start date (ISO format: YYYY-MM-DD)
    start_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

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

    def __repr__(self) -> str:
        return f"<Connection(id={self.id}, label='{self.label}', type='{self.type}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "start_date": self.start_date,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
