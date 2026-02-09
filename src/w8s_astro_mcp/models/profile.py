"""Profile model for storing astrological birth data and natal charts.

A Profile represents a person's birth data (date, time, location) and their
calculated natal chart. Supports multiple profiles for checking charts for
friends, family, or clients.
"""

from datetime import datetime, timezone
from typing import Optional
import json

from sqlalchemy import String, Float, DateTime, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class Profile(Base):
    """
    Astrological profile with birth data and cached natal chart.
    
    Design decisions:
    - natal_chart_json stores the complete swetest output as JSON
    - is_primary identifies the user's own chart (only one should be primary)
    - Timestamps track creation and updates for auditing
    """
    
    __tablename__ = "profiles"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Profile identification
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    
    # Birth data
    birth_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    birth_time: Mapped[str] = mapped_column(String(5), nullable=False)   # HH:MM
    
    # Birth location
    birth_location_name: Mapped[str] = mapped_column(String(200), nullable=False)
    birth_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    birth_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    birth_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Cached natal chart (JSON blob)
    # Structure: {"planets": {...}, "houses": {...}, "points": {...}, "metadata": {...}}
    natal_chart_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    natal_chart_cached_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Primary profile flag (user's own chart)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
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
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_profiles_name_primary', 'name', 'is_primary'),
    )
    
    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, name='{self.name}', birth_date='{self.birth_date}')>"
    
    def get_natal_chart(self) -> Optional[dict]:
        """
        Get the cached natal chart as a dictionary.
        
        Returns:
            Natal chart dict or None if not cached
        """
        if self.natal_chart_json is None:
            return None
        return json.loads(self.natal_chart_json)
    
    def set_natal_chart(self, chart_data: dict) -> None:
        """
        Cache a natal chart.
        
        Args:
            chart_data: Dictionary with planets, houses, points, metadata
        """
        self.natal_chart_json = json.dumps(chart_data)
        self.natal_chart_cached_at = datetime.now(timezone.utc)
    
    def clear_natal_chart(self) -> None:
        """Clear the cached natal chart."""
        self.natal_chart_json = None
        self.natal_chart_cached_at = None
    
    def to_dict(self) -> dict:
        """
        Convert profile to dictionary for API responses.
        
        Returns:
            Dictionary representation of the profile
        """
        return {
            "id": self.id,
            "name": self.name,
            "birth_date": self.birth_date,
            "birth_time": self.birth_time,
            "birth_location": {
                "name": self.birth_location_name,
                "latitude": self.birth_latitude,
                "longitude": self.birth_longitude,
                "timezone": self.birth_timezone,
            },
            "is_primary": self.is_primary,
            "has_natal_chart": self.natal_chart_json is not None,
            "natal_chart_cached_at": self.natal_chart_cached_at.isoformat() if self.natal_chart_cached_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
