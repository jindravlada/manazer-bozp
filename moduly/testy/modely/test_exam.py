"""Konkrétní připravená zkouška a její neměnný snapshot (TESTY-7)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestExam(Base):
    """Jedna zkouška zaměstnance podle definice Testu.

    Textové sloupce jsou snapshot v okamžiku přípravy. Pozdější úprava
    zaměstnance nebo definice Testu je nemění. Záznam se nevymazává.
    """

    __tablename__ = "test_exams"
    __table_args__ = (
        Index("ix_test_exams_employee_id", "employee_id"),
        Index("ix_test_exams_test_definition_id", "test_definition_id"),
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
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    examiner_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    employee_personal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    employee_last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    employee_title_before: Mapped[str] = mapped_column(String(50), default="")
    employee_title_after: Mapped[str] = mapped_column(String(50), default="")
    employee_display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    employee_workplace_name: Mapped[str] = mapped_column(String(150), default="")
    employee_roles_text: Mapped[str] = mapped_column(Text, default="")

    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    uses_written: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uses_oral: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_wrong_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seconds_per_question: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    written_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validity_value: Mapped[int] = mapped_column(Integer, nullable=False)
    validity_unit: Mapped[str] = mapped_column(String(20), nullable=False)

    # Průběh elektronické písemné části. Celkový stav zkoušky zůstává Zahájeno,
    # dokud další krok nevyhodnotí celou zkoušku včetně případné ústní části.
    written_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    written_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    written_finish_reason: Mapped[str] = mapped_column(String(20), default="", nullable=False)
