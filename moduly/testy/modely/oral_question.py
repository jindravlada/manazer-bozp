"""Ústní otázka (TESTY-5)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class OralQuestion(Base):
    """Jedna ústní otázka právě jednoho ústního okruhu.

    Nemá odpovědi A/B/C ani správnou odpověď. Záznam se nevymazává.
    """

    __tablename__ = "test_oral_questions"
    __table_args__ = (
        Index("ix_test_oral_questions_topic_id", "topic_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_oral_question_topics.id"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
