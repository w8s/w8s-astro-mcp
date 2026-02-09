"""HouseSystem model - reference table for astrological house calculation methods.

House systems define how the 12 houses are calculated in an astrological chart.
Different systems use different mathematical approaches to divide the ecliptic.

Common systems:
- Placidus (most popular in modern Western astrology)
- Whole Sign (oldest system, equal 30° houses)
- Koch (birthplace system)
- Regiomontanus, Campanus, Equal, etc.

This is a reference/lookup table - data is seeded at initialization, rarely changes.
"""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class HouseSystem(Base):
    """
    Reference table for house calculation systems.
    
    Each row represents a different mathematical method for calculating houses.
    The 'code' field matches the parameter passed to swetest -house flag.
    """
    
    __tablename__ = "house_systems"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Swetest parameter code (e.g., "P" for Placidus, "W" for Whole Sign)
    code: Mapped[str] = mapped_column(String(1), unique=True, nullable=False, index=True)
    
    # Display name
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Detailed explanation
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Is this the default system?
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<HouseSystem(code='{self.code}', name='{self.name}')>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
        }


# Seed data for house systems
# This will be used to populate the table on first run
HOUSE_SYSTEM_SEED_DATA = [
    {
        "code": "P",
        "name": "Placidus",
        "description": "Most popular system in modern Western astrology. Uses time-based divisions.",
        "is_default": True,
    },
    {
        "code": "W",
        "name": "Whole Sign",
        "description": "Oldest system. Each house is exactly 30°, starting from the Ascendant.",
        "is_default": False,
    },
    {
        "code": "K",
        "name": "Koch",
        "description": "Birthplace system. Popular in Central Europe.",
        "is_default": False,
    },
    {
        "code": "R",
        "name": "Regiomontanus",
        "description": "Space-based system. Popular in medieval astrology.",
        "is_default": False,
    },
    {
        "code": "C",
        "name": "Campanus",
        "description": "Prime vertical system. Used in horary astrology.",
        "is_default": False,
    },
    {
        "code": "E",
        "name": "Equal (from Ascendant)",
        "description": "Equal 30° houses starting from the Ascendant degree.",
        "is_default": False,
    },
    {
        "code": "A",
        "name": "Equal (from Aries)",
        "description": "Equal 30° houses starting from 0° Aries.",
        "is_default": False,
    },
]
