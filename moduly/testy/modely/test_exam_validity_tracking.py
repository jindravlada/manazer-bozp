"""Vypnuté sledování platnosti kombinace zaměstnanec × test (TESTY-12b)."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestExamValidityTracking(Base):
    """Záznam znamená „Nesledovat“.

    Chybějící kombinace se sleduje. Řádek nemění zkoušky, jejich výsledky
    ani datum platnosti. Nová zkouška stejné kombinace záznam smaže.
    """

    __tablename__ = "test_exam_validity_tracking"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "test_definition_id",
            name="uq_test_exam_validity_tracking_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_employees.id"),
        nullable=False,
    )
    test_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_definitions.id"),
        nullable=False,
    )
