"""Snapshot ústní otázky v pořadí konkrétní zkoušky."""

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestExamOralQuestion(Base):
    """Zmrazený text a název ústního okruhu. Z banky se znovu nečte."""

    __tablename__ = "test_exam_oral_questions"
    __table_args__ = (
        Index("ix_test_exam_oral_questions_exam_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exams.id"),
        nullable=False,
    )
    source_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_oral_questions.id"),
        nullable=False,
    )
    topic_name: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
