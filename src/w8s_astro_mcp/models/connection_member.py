"""ConnectionMember model - junction table linking profiles to connections.

Each row represents one person's membership in one connection.
A profile can appear in multiple connections; a connection has ≥2 members.

Design decisions:
- UNIQUE (connection_id, profile_id) — one row per person per connection
- ON DELETE CASCADE on connection_id — removing a connection removes its members
- ON DELETE RESTRICT on profile_id — cannot delete a profile that's in a connection
  (user must remove them from the connection first, or delete the connection)
- Minimum member count (≥2) enforced at application layer
"""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from w8s_astro_mcp.database import Base


class ConnectionMember(Base):
    """
    Junction table: one row per profile per connection.

    Removing a member invalidates any cached charts for that connection
    (handled at application layer via connection_charts.is_valid flag).
    """

    __tablename__ = "connection_members"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # The connection this member belongs to
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # The profile (person) who is a member
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Constraints
    __table_args__ = (
        # Each person appears at most once per connection
        UniqueConstraint('connection_id', 'profile_id', name='uq_connection_member'),
    )

    def __repr__(self) -> str:
        return (
            f"<ConnectionMember(id={self.id}, "
            f"connection_id={self.connection_id}, profile_id={self.profile_id})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "profile_id": self.profile_id,
        }
