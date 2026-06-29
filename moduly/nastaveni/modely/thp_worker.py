from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class ThpWorker(Base):
    __tablename__ = "thp_workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title_before: Mapped[str] = mapped_column(String(50), default="")
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title_after: Mapped[str] = mapped_column(String(50), default="")

    position: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    performs_controls: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def full_name(self) -> str:
        base = " ".join(
            part for part in [
                self.title_before,
                self.first_name,
                self.last_name,
            ]
            if part
        ).strip()

        if self.title_after:
            return f"{base}, {self.title_after}".strip()

        return base

    @property
    def display_name(self) -> str:
        return self.full_name
