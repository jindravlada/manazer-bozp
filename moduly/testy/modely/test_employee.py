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
    title_before: Mapped[str] = mapped_column(String(50), default="")
    title_after: Mapped[str] = mapped_column(String(50), default="")
    workplace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("workplaces.id"),
        nullable=False,
    )
    # Smí být nabídnut jako zkoušející, předseda nebo člen komise.
    # Konkrétní role se určuje až u zkoušky, ne u zaměstnance.
    may_examine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # male, female, nebo NULL u starších záznamů. Z jména se nedoplňuje.
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    @property
    def display_name(self) -> str:
        """Celé jméno včetně titulů, např. „Ing. Jan Novák, Ph.D.“."""
        from moduly.smlouvy_ozo.constants import format_ozo_display_name

        return format_ozo_display_name(
            self.title_before,
            self.first_name,
            self.last_name,
            self.title_after,
        )
