"""Snapshot písemné otázky v pořadí konkrétní zkoušky."""

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestExamWrittenQuestion(Base):
    """Zmrazený text, okruh a případná kopie obrázku zadání.

    ``source_question_id`` slouží jen k dohledání. Obsah se z banky znovu nečte.
    """

    __tablename__ = "test_exam_written_questions"
    __table_args__ = (
        Index("ix_test_exam_written_questions_exam_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exams.id"),
        nullable=False,
    )
    source_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_written_questions.id"),
        nullable=False,
    )
    topic_name: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    image_stored_path: Mapped[str] = mapped_column(String(500), default="")
    image_sha256: Mapped[str] = mapped_column(String(64), default="")
