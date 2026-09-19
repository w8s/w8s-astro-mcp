"""DismissedNotice model - notices the user has chosen to stop seeing.

A notice is identified by a stable key (for example "natal-utc-fix"). ``detail`` records what the
user had seen when they dismissed it, as a JSON list (for the natal-chart notice: the profile IDs
that were stale at the time). The notice comes back if something *different* needs attention.

Design decisions:
- One row per notice key (UNIQUE), replaced when the user dismisses again
- Lives in the database rather than a config file: the project moved from config.json to SQLite in
  v0.9, and ``detail`` refers to profile IDs that only make sense next to this database
- New table only; existing databases pick it up automatically (create_all), no migration
"""

import json
from datetime import datetime, timezone
from typing import List

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class DismissedNotice(Base):
    """A notice the user has dismissed."""

    __tablename__ = "dismissed_notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Stable identifier of the notice, e.g. "natal-utc-fix"
    notice_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # JSON list describing what the user had seen (e.g. stale profile IDs)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    dismissed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def detail_list(self) -> List[int]:
        """The stored detail as a list of integers."""
        return [int(item) for item in json.loads(self.detail or "[]")]

    def __repr__(self) -> str:
        return f"<DismissedNotice(notice_key={self.notice_key!r}, detail={self.detail})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "notice_key": self.notice_key,
            "detail": self.detail_list(),
            "dismissed_at": self.dismissed_at.isoformat() if self.dismissed_at else None,
        }
