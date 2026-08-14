"""Modely Externích auditů (EA-0)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
    EXTERNAL_AUDIT_STATUS_PLANNED,
    EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
)


class ExternalAudit(Base):
    __tablename__ = "external_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default=EXTERNAL_AUDIT_TYPE_SURVEILLANCE
    )
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=EXTERNAL_AUDIT_STATUS_PLANNED
    )
    remind_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    organization_ico: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    organization_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    organization_address: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    organization_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class ExternalAuditVisit(Base):
    __tablename__ = "external_audit_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_audits.id"),
        nullable=False,
        index=True,
    )
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_from: Mapped[str | None] = mapped_column(String(8), nullable=True)
    time_to: Mapped[str | None] = mapped_column(String(8), nullable=True)

    workplace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    workplace_name_snapshot: Mapped[str] = mapped_column(
        String(150), nullable=False, default=""
    )
    workplace_address_snapshot: Mapped[str] = mapped_column(
        String(250), nullable=False, default=""
    )

    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class ExternalAuditParticipant(Base):
    __tablename__ = "external_audit_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_audits.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(
        String(250), nullable=False, default=""
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class ExternalAuditVisitParticipant(Base):
    __tablename__ = "external_audit_visit_participants"
    __table_args__ = (
        UniqueConstraint(
            "visit_id",
            "participant_id",
            name="uq_external_audit_visit_participant",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_audit_visits.id"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_audit_participants.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ExternalAuditFinding(Base):
    __tablename__ = "external_audit_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_audits.id"),
        nullable=False,
        index=True,
    )
    finding_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    resolution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class ExternalAuditFindingTaskLink(Base):
    __tablename__ = "external_audit_finding_task_links"
    __table_args__ = (
        UniqueConstraint(
            "finding_id",
            "task_id",
            name="uq_external_audit_finding_task",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_audit_findings.id"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
