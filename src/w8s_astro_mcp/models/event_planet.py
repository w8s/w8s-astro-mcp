"""EventPlanet model - planetary positions in an event chart."""

from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class EventPlanet(Base):
    """Planetary position in an event chart. One row per planet per event."""

    __tablename__ = "event_planets"

    id: Mapped[int] = mapped_column(primary_key=True)

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    planet: Mapped[str] = mapped_column(String(20), nullable=False)

    degree: Mapped[int] = mapped_column(Integer, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sign: Mapped[str] = mapped_column(String(20), nullable=False)
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False)
    house_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_retrograde: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_event_planets_event_sign", "event_id", "sign"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventPlanet(id={self.id}, event_id={self.event_id}, "
            f"planet='{self.planet}', position={self.degree}°{self.sign})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "planet": self.planet,
            "degree": self.degree,
            "minutes": self.minutes,
            "seconds": self.seconds,
            "sign": self.sign,
            "absolute_position": self.absolute_position,
            "house_number": self.house_number,
            "is_retrograde": self.is_retrograde,
        }

    @property
    def formatted_position(self) -> str:
        return f"{self.degree}°{self.minutes}'{int(self.seconds)}\" {self.sign}"
