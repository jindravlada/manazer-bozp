from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.vysetrovani_mu.constants import (
    DEFAULT_EVENT_CHARACTER,
    DEFAULT_MU_STATUS,
    DEFAULT_SOURCE_TYPE,
)


class MuInvestigation(Base):
    __tablename__ = "mu_investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    number: Mapped[str] = mapped_column(String(30), default="")
    title: Mapped[str] = mapped_column(String(250), default="")
    event_character: Mapped[str] = mapped_column(String(80), default=DEFAULT_EVENT_CHARACTER, nullable=False)

    source_type: Mapped[str] = mapped_column(String(30), default=DEFAULT_SOURCE_TYPE, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_label: Mapped[str] = mapped_column(String(250), default="")

    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=DEFAULT_MU_STATUS, nullable=False)

    lead_thp_worker_id: Mapped[int | None] = mapped_column("lead_person_id", Integer, nullable=True)
    lead_thp_worker_name: Mapped[str] = mapped_column("lead_person_name", String(150), default="")

    short_description: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
