"""Snapshot zkoušejícího nebo člena komise u konkrétní zkoušky."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.testy.constants import EMPLOYEE_SOURCE_TEST_EMPLOYEE


class TestExamExaminer(Base):
    """Osoba v roli Zkoušející, Předseda nebo Člen.

    ``display_name`` je snímek jména v okamžiku přípravy.
    """

    __tablename__ = "test_exam_examiners"
    __table_args__ = (
        Index("ix_test_exam_examiners_exam_id", "exam_id"),
        CheckConstraint(
            "employee_source IN ('test_employee', 'thp_worker')",
            name="ck_test_exam_examiners_employee_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_exams.id"),
        nullable=False,
    )
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
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
