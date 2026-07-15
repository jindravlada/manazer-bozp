from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


PROPOSAL_STATUS_PENDING = "pending"
PROPOSAL_STATUS_REJECTED = "rejected"
PROPOSAL_STATUS_UNASSIGNED = "unassigned"
PROPOSAL_STATUS_INCORPORATED = "incorporated"

PROPOSAL_STATUS_LABELS = {
    PROPOSAL_STATUS_PENDING: "Čeká na odborné posouzení",
    PROPOSAL_STATUS_REJECTED: "Zamítnuto",
    PROPOSAL_STATUS_UNASSIGNED: "Nezařazeno",
    PROPOSAL_STATUS_INCORPORATED: "Zapracováno",
}

UNASSIGNED_PROPOSAL_STATUS = PROPOSAL_STATUS_UNASSIGNED
UNASSIGNED_PROPOSAL_STATUS_LABEL = PROPOSAL_STATUS_LABELS[PROPOSAL_STATUS_UNASSIGNED]


class AiUnassignedProposal(Base):
    """
    Návrh z AI oponentního posouzení – evidence pro pozdější zpracování
    nebo nezařazený návrh bez platného rodiče v hierarchii.
    """

    __tablename__ = "ai_unassigned_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_peer_review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    area: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parent_export_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    exposed_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=PROPOSAL_STATUS_UNASSIGNED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
