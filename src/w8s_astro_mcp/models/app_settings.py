"""AppSettings model - application-level configuration.

Stores app-wide settings like which profile is the current user.
Only one row exists in this table (id=1).

Design decisions:
- Single row table (id always = 1)
- current_profile_id can be NULL (no profile selected yet)
- ON DELETE SET NULL ensures app doesn't break if user deletes their profile
- Future: Can add other app settings (theme, defaults, etc.)
"""

from typing import Optional

from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class AppSettings(Base):
    """
    Application settings.
    
    Only one row exists (id=1). Contains app-level configuration
    like which profile is the current user.
    """
    
    __tablename__ = "app_settings"
    
    # Always id=1 (single row table)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    
    # Which profile is "me" right now?
    # NULL = no profile selected yet
    # SET NULL = if user deletes their profile, reset to NULL
    current_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<AppSettings(current_profile_id={self.current_profile_id})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "current_profile_id": self.current_profile_id,
        }
