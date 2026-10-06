"""Zvolená odpověď zaměstnance u snapshotové písemné otázky."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestExamWrittenChoice(Base):
    """Jedna aktuální volba k jedné snapshotové otázce.

    Ukládá se proti řádku snapshotu, ne proti živé bance. Nová volba nahrazuje
    předchozí. Správnost se sem nekopíruje; zůstává na snapshotové odpovědi
    a zaměstnanci se během testu neukazuje.
    """

    __tablename__ = "test_exam_written_choices"
    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "exam_question_id",
            name="uq_test_exam_written_choices_question",
        ),
        Index("ix_test_exam_written_choices_exam_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exams.id"),
        nullable=False,
    )
    exam_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exam_written_questions.id"),
        nullable=False,
    )
    exam_answer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exam_written_answers.id"),
        nullable=False,
    )
    selected_letter: Mapped[str] = mapped_column(String(1), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
