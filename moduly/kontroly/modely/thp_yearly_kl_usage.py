from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class ThpYearlyKlUsage(Base):
    __tablename__ = "thp_yearly_kl_usage"
    __table_args__ = (
        UniqueConstraint("year", "thp_worker_id", name="uq_thp_yearly_kl_usage"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    thp_worker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    thp_worker_name: Mapped[str] = mapped_column(String(150), default="")

    kl_01: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_02: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_03: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_04: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_05: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_06: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_07: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_08: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_09: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_10: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_11: Mapped[bool] = mapped_column(Boolean, default=False)
    kl_12: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    @classmethod
    def kl_field_name(cls, kl_index: int) -> str:
        return f"kl_{kl_index:02d}"

    def get_kl_used(self, kl_index: int) -> bool:
        return bool(getattr(self, self.kl_field_name(kl_index), False))

    def set_kl_used(self, kl_index: int, used: bool) -> None:
        setattr(self, self.kl_field_name(kl_index), used)

    def kl_flags(self) -> dict[int, bool]:
        return {index: self.get_kl_used(index) for index in range(1, 13)}
