"""Zastřešující kontrolní orgán katalogu Státního dozoru."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.statni_dozor.constants import AUTHORITY_ORIGIN_MANUAL


class ControlAuthority(Base):
    __tablename__ = "control_authorities"
    __table_args__ = (
        Index("uq_control_authorities_code", "code", unique=True),
        Index("ix_control_authorities_active", "active"),
        Index("ix_control_authorities_display_order", "display_order"),
        Index(
            "uq_control_authorities_external_key",
            "external_key",
            unique=True,
            sqlite_where=text("external_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
