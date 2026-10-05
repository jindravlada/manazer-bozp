"""Zaměstnanec pro přezkušování (TESTY-2a)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestEmployee(Base):
    """Evidence zaměstnance pro testy.

    Osobní číslo je text, ne číslo: import z Excelu musí zachovat úvodní nuly
    a podle něj jednoznačně najít existující záznam. Hodnota je jedinečná
    i u neaktivních zaměstnanců, aby se při aktualizaci nesmíchali dva lidé.
    """

    __tablename__ = "test_employees"
    __table_args__ = (
        UniqueConstraint(
            "personal_number",
            name="uq_test_employees_personal_number",
        ),
        Index("ix_test_employees_workplace_id", "workplace_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    personal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    workplace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("workplaces.id"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
