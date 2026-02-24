"""EventHouse model - house cusps in an event chart."""

from sqlalchemy import String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class EventHouse(Base):
    """House cusp position in an event chart. One row per house per event."""

    __tablename__ = "event_houses"

    id: Mapped[int] = mapped_column(primary_key=True)

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    house_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12

    degree: Mapped[int] = mapped_column(Integer, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sign: Mapped[str] = mapped_column(String(20), nullable=False)
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_event_houses_event_house", "event_id", "house_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventHouse(id={self.id}, event_id={self.event_id}, "
            f"house={self.house_number}, cusp={self.degree}°{self.sign})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "house_number": self.house_number,
            "degree": self.degree,
            "minutes": self.minutes,
            "seconds": self.seconds,
            "sign": self.sign,
            "absolute_position": self.absolute_position,
        }
