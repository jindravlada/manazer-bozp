from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


PACKAGE_STATUS_PENDING = "pending"
PACKAGE_STATUS_REJECTED = "rejected"
PACKAGE_STATUS_INCORPORATED = "incorporated"

PACKAGE_STATUS_LABELS = {
    PACKAGE_STATUS_PENDING: "Čeká na odborné posouzení",
    PACKAGE_STATUS_REJECTED: "Zamítnuto",
    PACKAGE_STATUS_INCORPORATED: "Zapracováno",
}


class AiProposalPackageRecord(Base):
    """Ucelený návrhový balík z AI oponentury (schema 2.0)."""

    __tablename__ = "ai_proposal_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_peer_review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    package_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    package_type: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    target_event_export_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=PACKAGE_STATUS_PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
