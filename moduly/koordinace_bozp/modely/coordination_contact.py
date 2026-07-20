"""Kontaktní osoba koordinace (COORD-010)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import DEFAULT_CONTACT_TYPE


class CoordinationContact(Base):
    """Důležitý kontakt pro průběh prací / mimořádné události.

    Údaje jména, organizace, role, telefonu a e-mailu jsou snapshot – nezávisí
    na pozdější změně účastníka schůzky nebo zaměstnavatele.
    """

    __tablename__ = "coordination_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("coordination_participants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    employer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contact_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_CONTACT_TYPE,
    )
    custom_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    employer_name: Mapped[str] = mapped_column(String(250), default="")
    role: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
