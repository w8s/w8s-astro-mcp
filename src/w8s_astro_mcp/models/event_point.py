"""EventPoint model - angles and special points in an event chart."""

from sqlalchemy import String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class EventPoint(Base):
    """Angle or special point in an event chart (ASC, MC, etc.)."""

    __tablename__ = "event_points"

    id: Mapped[int] = mapped_column(primary_key=True)

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    point_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ASC, MC, etc.

    degree: Mapped[int] = mapped_column(Integer, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sign: Mapped[str] = mapped_column(String(20), nullable=False)
    absolute_position: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_event_points_event_type", "event_id", "point_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventPoint(id={self.id}, event_id={self.event_id}, "
            f"point='{self.point_type}', position={self.degree}°{self.sign})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "point_type": self.point_type,
            "degree": self.degree,
            "minutes": self.minutes,
            "seconds": self.seconds,
            "sign": self.sign,
            "absolute_position": self.absolute_position,
        }
