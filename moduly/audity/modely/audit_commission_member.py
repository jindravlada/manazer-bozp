from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditCommissionMember(Base):
    __tablename__ = "audit_commission_members"
    __table_args__ = (Index("ix_audit_commission_members_audit_id", "audit_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)

    record_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    thp_worker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    role_text: Mapped[str | None] = mapped_column(String(150), nullable=True)
    note_text: Mapped[str | None] = mapped_column(String(250), nullable=True)

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
