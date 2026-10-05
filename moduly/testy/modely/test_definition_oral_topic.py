"""Ústní okruh zařazený do definice Testu."""

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestDefinitionOralTopic(Base):
    """Kolik ústních otázek se má z okruhu později vybrat.

    Jeden okruh je v jednom Testu nejvýše jednou.
    """

    __tablename__ = "test_definition_oral_topics"
    __table_args__ = (
        UniqueConstraint(
            "test_id",
            "topic_id",
            name="uq_test_definition_oral_topics_topic",
        ),
        Index("ix_test_definition_oral_topics_test_id", "test_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_definitions.id"),
        nullable=False,
    )
    topic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_oral_question_topics.id"),
        nullable=False,
    )
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
