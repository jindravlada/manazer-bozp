from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


UNASSIGNED_PROPOSAL_STATUS = "unassigned"
UNASSIGNED_PROPOSAL_STATUS_LABEL = "Nezařazený návrh"


class AiUnassignedProposal(Base):
    """
    Návrh z AI, který nelze bezpečně zařadit do hierarchie
    (chybí nebo neplatné parent_export_id).
    """

    __tablename__ = "ai_unassigned_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_peer_review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    area: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parent_export_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=UNASSIGNED_PROPOSAL_STATUS,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
