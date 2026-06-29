from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.audity.constants import DEFAULT_AUDIT_STATUS


class InternalAudit(Base):
    __tablename__ = "internal_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    number: Mapped[str] = mapped_column(String(30), default="")
    audit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    workplace: Mapped[str] = mapped_column(String(150), default="")
    title: Mapped[str] = mapped_column(String(250), default="")
    status: Mapped[str] = mapped_column(String(30), default=DEFAULT_AUDIT_STATUS, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
