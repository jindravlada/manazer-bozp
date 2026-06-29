from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class ThpMonthlyControl(Base):
    __tablename__ = "thp_monthly_controls"
    __table_args__ = (
        UniqueConstraint("year", "month", "thp_worker_id", name="uq_thp_monthly_control"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    thp_worker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    thp_worker_name: Mapped[str] = mapped_column(String(150), default="")

    status: Mapped[str] = mapped_column(String(20), default="none")
    kl_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
