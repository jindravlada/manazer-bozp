from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.nastaveni.constants.workplace_audit_constants import (
    DEFAULT_WORKPLACE_AUDIT_ENABLED,
    DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS,
)
from moduly.nastaveni.sluzby.workplace_audit_planning import default_preferred_months_json


class Workplace(Base):
    __tablename__ = "workplaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(250), default="")
    note: Mapped[str] = mapped_column(String(250), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    audit_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_WORKPLACE_AUDIT_ENABLED,
        nullable=False,
    )
    audit_interval_months: Mapped[int] = mapped_column(
        Integer,
        default=DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS,
        nullable=False,
    )
    preferred_months_json: Mapped[str] = mapped_column(
        Text,
        default=default_preferred_months_json,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
