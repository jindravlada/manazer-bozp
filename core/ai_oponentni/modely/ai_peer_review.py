from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AiPeerReview(Base):
    """Evidence jedné konzultace s externí AI (obecné pro celý Manažer BOZP)."""

    __tablename__ = "ai_peer_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    exported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    export_file_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    export_id_map_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    export_scope: Mapped[str] = mapped_column(String(32), default="full", nullable=False)
    batch_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    selected_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_object_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    response_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unassigned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiPeerReviewBatch(Base):
    """Jedna dávka patřící ke společné konzultaci / exportu."""

    __tablename__ = "ai_peer_review_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_peer_review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    object_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    recommended_limit_exceeded: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
