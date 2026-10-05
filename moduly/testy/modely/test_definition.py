"""Definice Testu (TESTY-6). Nahrazuje historický pojem Profil."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestDefinition(Base):
    """Pravidla, podle kterých se později vytvoří konkrétní zkouška.

    Záznam se nevymazává. Platnost je kalendářní počet měsíců nebo let,
    nikoli pevný počet dnů. Skladba okruhů je v samostatných tabulkách.
    """

    __tablename__ = "test_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uses_written: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_wrong_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seconds_per_question: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    uses_oral: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    examiner_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    validity_value: Mapped[int] = mapped_column(Integer, nullable=False)
    validity_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
