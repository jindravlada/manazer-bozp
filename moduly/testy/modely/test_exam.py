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
    # Příprava zkoušky datum ukládá. Prázdná hodnota v přehledu platnosti
    # znamená úspěšnou zkoušku bez data konce platnosti.
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
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

    # Průběh a uložené vyhodnocení elektronické písemné části.
    # Čísla a výsledek vzniknou až při definitivním ukončení, ze snapshotu
    # této zkoušky. Prázdné hodnoty neznamenají Vyhověl ani Nevyhověl.
    written_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Poslední zaznamenaný efektivní čas běžící elektronické zkoušky.
    # Posouvá se jen dopředu. NULL u starších řádků a mimo elektronický průběh.
    written_time_mark: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    written_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    written_finish_reason: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    written_question_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    written_correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    written_incorrect_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    written_unanswered_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    written_allowed_wrong_answers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    written_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exam_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    written_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Jen dodatečný zápis neúspěchu. Prázdná hodnota není stav Vyhověl.
    oral_failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # NULL i prázdný řetězec: způsob provedení ještě nebyl zvolen.
    # Jinak electronic, nebo paper.
    written_mode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default="",
    )
    # Aktuální podepsaný protokol. Prázdné znamená nepřipojeno.
    # Starší kopie v přílohách se při výměně ani odebrání nemažou.
    signed_protocol_attachment_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    # Konkrétní důvod technického ukončení. Prázdné u běžné zkoušky.
    # Rozpracované odpovědi se kvůli němu nemažou a do hodnocení nevstupují.
    written_technical_detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
