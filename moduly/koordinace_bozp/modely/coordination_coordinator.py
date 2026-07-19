"""Pověřený koordinátor BOZP u koordinace (COORD-005)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class CoordinationCoordinator(Base):
    """Koordinátor vybraný z účastníků schůzky (snapshot vazby, ne jména)."""

    __tablename__ = "coordination_coordinators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_participants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
