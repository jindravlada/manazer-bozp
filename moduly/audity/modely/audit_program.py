from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.audity.constants import (
    DEFAULT_AUDIT_PROGRAM_STATUS,
    DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS,
    DEFAULT_AUDIT_PROGRAM_VISIT_STATUS,
)


class AuditProgram(Base):
    __tablename__ = "audit_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(30), default="")
    name: Mapped[str] = mapped_column(String(250), default="")
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_AUDIT_PROGRAM_STATUS,
        nullable=False,
    )
    standards_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    manual_planning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AuditProgramWorkplace(Base):
    __tablename__ = "audit_program_workplaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")
    audit_interval_months: Mapped[int] = mapped_column(Integer, default=12)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")


class AuditProgramVisit(Base):
    __tablename__ = "audit_program_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_AUDIT_PROGRAM_VISIT_STATUS,
        nullable=False,
    )
    audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class AuditProgramVisitProcess(Base):
    __tablename__ = "audit_program_visit_processes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    process_id: Mapped[str] = mapped_column(String(80), default="")
    process_name: Mapped[str] = mapped_column(String(250), default="")
    standards_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS,
        nullable=False,
    )
    audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
