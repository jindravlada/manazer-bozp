"""Snapshot jedné odpovědi A/B/C u písemné otázky zkoušky."""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestExamWrittenAnswer(Base):
    """Odpověď v pořadí, v jakém ji uvidí tato zkouška.

    Správnost je uložená zde. Z aktuální banky se znovu neodvozuje.
    Obrázek je vlastní kopie, ne odkaz na přílohu banky.
    """

    __tablename__ = "test_exam_written_answers"
    __table_args__ = (
        UniqueConstraint(
            "exam_question_id",
            "letter",
            name="uq_test_exam_written_answers_letter",
        ),
        Index("ix_test_exam_written_answers_question_id", "exam_question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exam_written_questions.id"),
        nullable=False,
    )
    letter: Mapped[str] = mapped_column(String(1), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_stored_path: Mapped[str] = mapped_column(String(500), default="")
    image_sha256: Mapped[str] = mapped_column(String(64), default="")
