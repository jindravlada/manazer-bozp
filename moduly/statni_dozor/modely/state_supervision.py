"""Hlavní záznam kontroly státního dozoru."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.statni_dozor.constants import DEFAULT_STATUS


class StateSupervision(Base):
    __tablename__ = "state_supervisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=DEFAULT_STATUS,
        index=True,
    )

    authority_ico: Mapped[str | None] = mapped_column(String(20), nullable=True)
    authority_name: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    authority_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authority_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    authority_office_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    authority_office_name_snapshot: Mapped[str | None] = mapped_column(
        String(250), nullable=True
    )

    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    workplace_name_snapshot: Mapped[str] = mapped_column(
        String(150), nullable=False, default=""
    )
    workplace_address_snapshot: Mapped[str] = mapped_column(
        String(250), nullable=False, default=""
    )

    notification_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    announced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_union_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    management_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_start_place: Mapped[str | None] = mapped_column(String(250), nullable=True)
    planned_control_place: Mapped[str | None] = mapped_column(String(250), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    file_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    preparation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_of_attorney_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    power_of_attorney_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    protocol_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    protocol_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    objections_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    objections_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    objections_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_evidence_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    authority_confirmation_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
