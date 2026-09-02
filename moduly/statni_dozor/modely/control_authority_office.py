"""Pracoviště kontrolního orgánu — konkrétní příslušné pracoviště."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.statni_dozor.constants import AUTHORITY_ORIGIN_MANUAL


class ControlAuthorityOffice(Base):
    __tablename__ = "control_authority_offices"
    __table_args__ = (
        Index("ix_control_authority_offices_authority_id", "authority_id"),
        Index("ix_control_authority_offices_active", "active"),
        Index("ix_control_authority_offices_display_order", "display_order"),
        Index(
            "uq_control_authority_offices_external_key",
            "external_key",
            unique=True,
            sqlite_where=text("external_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    authority_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("control_authorities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    territorial_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    office_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AUTHORITY_ORIGIN_MANUAL
    )
    external_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
