"""Písemná otázka v bance testů (TESTY-4)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class WrittenQuestion(Base):
    """Jedna písemná otázka právě jednoho okruhu.

    Záznam se nevymazává. Pro nové testy se později použijí jen aktivní otázky.
    """

    __tablename__ = "test_written_questions"
    __table_args__ = (
        Index("ix_test_written_questions_topic_id", "topic_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_written_question_topics.id"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    image_attachment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
