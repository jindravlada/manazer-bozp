from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class BozpInspectionCommissionMember(Base):
    __tablename__ = "bozp_inspection_commission_members"
    __table_args__ = (Index("ix_bozp_inspection_commission_members_inspection_id", "inspection_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(Integer, nullable=False)

    record_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    thp_worker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    role_text: Mapped[str | None] = mapped_column(String(150), nullable=True)

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
