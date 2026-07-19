"""Příloha koordinace – rizika dodavatele a další (COORD-006)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import ATTACHMENT_TYPE_CONTRACTOR_RISKS


class CoordinationAttachment(Base):
    """Soubor zkopírovaný do spravovaného úložiště aplikace."""

    __tablename__ = "coordination_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coordination_employer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    attachment_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
