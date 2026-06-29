from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditParticipant(Base):
    __tablename__ = "audit_participants"
    __table_args__ = (Index("ix_audit_participants_audit_id", "audit_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)

    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(150), default="")
    role: Mapped[str] = mapped_column(String(150), default="")
    organization: Mapped[str] = mapped_column(String(150), default="")

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
