"""Evidence vydání Pravidel bezpečné práce (PBP-5a, PBP-5c)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base

# Sentinel: vydání pro profesi nemá konkrétní ohroženou skupinu v rozsahu.
PBP_EDITION_NO_ENDANGERED_GROUP = 0


class PravidlaBezpecnePraceEdition(Base):
    """Jedno vydání Pravidel bezpečné práce pro daný rozsah.

    Rozsah je buď přímá ohrožená skupina (``profession_id`` je NULL),
    nebo profese (``profession_id`` nastaveno, ``endangered_group_id`` = 0).
    """

    __tablename__ = "pravidla_bezpecne_prace_editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    endangered_group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    profession_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    operation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    workplace_part_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    export_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    rules: Mapped[list[PravidlaBezpecnePraceEditionRule]] = relationship(
        "PravidlaBezpecnePraceEditionRule",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="PravidlaBezpecnePraceEditionRule.sort_order",
    )


class PravidlaBezpecnePraceEditionRule(Base):
    """Snapshot jednoho pravidla v konkrétním vydání."""

    __tablename__ = "pravidla_bezpecne_prace_edition_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pravidla_bezpecne_prace_editions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    severity_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    measure_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unsuitable_for_employee: Mapped[bool] = mapped_column(Boolean, default=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    edition: Mapped[PravidlaBezpecnePraceEdition] = relationship(
        "PravidlaBezpecnePraceEdition",
        back_populates="rules",
    )
