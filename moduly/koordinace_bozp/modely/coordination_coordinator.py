"""Pověřený koordinátor BOZP u koordinace (COORD-005 / UX-COORD-2)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class CoordinationCoordinator(Base):
    """Koordinátor BOZP – z účastníků nebo zadaný ručně.

    Jméno, organizace, funkce, telefon a e-mail jsou snapshot – nezávisí na
    pozdější změně účastníka schůzky.
    """

    __tablename__ = "coordination_coordinators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    participant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("coordination_participants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    employer_name: Mapped[str] = mapped_column(String(250), default="")
    role: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
