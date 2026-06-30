from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Task(Base):
    """
    Globální opatření / úkol systému.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(30), default="Aktivní", nullable=False)
    priority: Mapped[str] = mapped_column(String(30), default="Normální")

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    responsible_person: Mapped[str] = mapped_column(String(150), default="")
    responsible_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")

    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    requires_verification: Mapped[bool] = mapped_column(Boolean, default=False)

    check_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checked_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_by_name: Mapped[str] = mapped_column(String(150), default="")

    canceled: Mapped[bool] = mapped_column(Boolean, default=False)

    note: Mapped[str] = mapped_column(Text, default="")

    source_module: Mapped[str] = mapped_column(String(50), default="manual")
    source_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_type: Mapped[str] = mapped_column(String(50), default="corrective")
    source_check_code: Mapped[str] = mapped_column(String(100), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    @property
    def computed_status(self) -> str:
        if self.canceled:
            return "Zrušeno"

        if self.completed:
            if not self.requires_verification:
                return "Ukončeno"
            if self.checked_date:
                return "Ukončeno"
            return "Splněno - čeká na kontrolu"

        return "Aktivní"
