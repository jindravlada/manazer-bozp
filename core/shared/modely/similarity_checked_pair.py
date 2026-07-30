"""Evidence zkontrolovaných dvojic podobných záznamů (SIMILARITY-3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class SimilarityCheckedPair(Base):
    """Uživatelsky zkontrolovaná dvojice podobných záznamů.

    ``left_entity_id`` / ``right_entity_id`` jsou vždy normalizované
    (left = min, right = max), aby 15+28 a 28+15 byly stejný záznam.
    """

    __tablename__ = "similarity_checked_pairs"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "left_entity_id",
            "right_entity_id",
            name="uq_similarity_checked_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    left_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    right_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)

    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    checked_by: Mapped[str] = mapped_column(String(150), default="", nullable=False)
