"""AppSettings model - application-level configuration.

Stores app-wide settings like who the owner (conversation operator) is.
Only one row exists in this table (id=1).

Design decisions:
- Single row table (id always = 1)
- owner_profile_id can be NULL (not yet configured)
- ON DELETE SET NULL ensures app doesn't break if owner deletes their profile
- owner_profile_id is the stable identity of the human using this server —
  set once during setup, not switched during normal operation
- Future: Can add other app settings (theme, defaults, etc.)
"""

from typing import Optional

from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class AppSettings(Base):
    """
    Application settings.

    Only one row exists (id=1). Contains app-level configuration.

    owner_profile_id is the stable identity of the human operating this server.
    It is set once during setup and should not change during normal use.
    All tools default to the owner's profile when no profile_id is supplied.
    """

    __tablename__ = "app_settings"

    # Always id=1 (single row table)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Who is the human on the other end of this conversation?
    # NULL = not yet configured (run setup_owner to set)
    # SET NULL = if owner deletes their profile, resets to NULL
    owner_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<AppSettings(owner_profile_id={self.owner_profile_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "owner_profile_id": self.owner_profile_id,
        }
