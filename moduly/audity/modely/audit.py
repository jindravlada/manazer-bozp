from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.audity.constants import (
    DEFAULT_AUDIT_SPIS_STATUS,
    DEFAULT_AUDIT_TYPE,
)


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    number: Mapped[str] = mapped_column(String(30), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    finished_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=DEFAULT_AUDIT_SPIS_STATUS, nullable=False)
    audit_type: Mapped[str] = mapped_column(String(30), default=DEFAULT_AUDIT_TYPE, nullable=False)

    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")
    title: Mapped[str] = mapped_column(String(250), default="")

    program_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    program_visit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    silne_stranky: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # AUDIT-SNAPSHOT-0: nullable označení snapshotované metodiky (zatím nepoužíváno).
    methodology_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    questions_frozen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    methodology_generation: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # AUDIT-SNAPSHOT-URGENT-1: integritní manifest zmrazeného snapshotu.
    snapshot_question_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_integrity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # AUDIT-INTRO-1: volitelný text změn od posledního auditu (záložka Úvod).
    changes_since_last: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AUDIT-CONCLUSION-1: uživatelský závěr auditu (povinný při dokončení).
    conclusion_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AUDIT-METHOD-SUPPORT-SNAPSHOT-1: samostatná integrita metodické podpory.
    support_snapshot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    support_integrity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
