"""Vypnuté sledování platnosti kombinace zaměstnanec × test (TESTY-12b)."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.testy.constants import EMPLOYEE_SOURCE_TEST_EMPLOYEE


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
        CheckConstraint(
            "employee_source IN ('test_employee', 'thp_worker')",
            name="ck_test_exam_validity_tracking_employee_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_employees.id"),
        nullable=False,
    )
    employee_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        server_default=text(f"'{EMPLOYEE_SOURCE_TEST_EMPLOYEE}'"),
    )
    test_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_definitions.id"),
        nullable=False,
    )
