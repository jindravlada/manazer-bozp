from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class FindingSettlementOverview(Base):
    """Jeden předložený přehled vypořádání. Řada je samostatná podle source_type.

    Uložený řádek se dál nemění. Aplikace k přehledům nemá mazání.
    """

    __tablename__ = "finding_settlement_overviews"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "sequence_number",
            name="uq_finding_settlement_overviews_source_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    presented_at: Mapped[date] = mapped_column(Date, nullable=False)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    settled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    in_process_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    type_counts_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class FindingSettlementOverviewItem(Base):
    """Neměnný snímek jednoho zjištění v přehledu.

    Texty, stav, datum vypořádání i stav úkolu jsou kopie v okamžiku vzniku.
    Pozdější úprava zjištění, auditu nebo úkolu tento řádek nemění.
    """

    __tablename__ = "finding_settlement_overview_items"
    __table_args__ = (
        Index("ix_finding_settlement_overview_items_overview", "overview_id"),
        Index("ix_finding_settlement_overview_items_finding", "finding_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    overview_id: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_id: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_number: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    audit_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    finding_type: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    process_label: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    verification_area_label: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    resolved_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    task_status: Mapped[str] = mapped_column(String(40), default="", nullable=False)

    settled_since_previous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    still_unsettled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reopened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resettled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
