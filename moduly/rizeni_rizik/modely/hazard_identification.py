from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.constants import DEFAULT_HAZARD_IDENTIFICATION_STATUS


class HazardIdentification(Base):
    __tablename__ = "hazard_identifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)

    operation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_name: Mapped[str] = mapped_column(String(150), default="")

    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")

    workplace_part_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_part_name: Mapped[str] = mapped_column(String(150), default="")

    responsible_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsible_person_name: Mapped[str] = mapped_column(String(150), default="")

    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_HAZARD_IDENTIFICATION_STATUS,
        nullable=False,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
