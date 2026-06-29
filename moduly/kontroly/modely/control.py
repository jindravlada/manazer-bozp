from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    inspection_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")

    inspector_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inspector_name: Mapped[str] = mapped_column(String(150), default="")

    result: Mapped[str] = mapped_column(String(30), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    sd_reference: Mapped[str] = mapped_column(String(200), default="")

    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
