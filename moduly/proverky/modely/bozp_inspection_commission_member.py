from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class BozpInspectionCommissionMember(Base):
    __tablename__ = "bozp_inspection_commission_members"
    __table_args__ = (Index("ix_bozp_inspection_commission_members_inspection_id", "inspection_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(Integer, nullable=False)

    team_member_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    thp_worker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    person_name: Mapped[str] = mapped_column(String(200), default="")

    role_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    role_name: Mapped[str] = mapped_column(String(150), default="")

    mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    participated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ad_hoc: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
