"""Jedna ze tří odpovědí písemné otázky."""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class WrittenQuestionAnswer(Base):
    """Odpověď A, B nebo C. Text a obrázek se nemíchají v jedné otázce."""

    __tablename__ = "test_written_question_answers"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "position",
            name="uq_test_written_question_answers_position",
        ),
        Index("ix_test_written_question_answers_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_written_questions.id"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    image_attachment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
