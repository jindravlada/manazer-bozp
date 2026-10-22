from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class ThpWorker(Base):
    """THP pracovník. Tabulka je připravená jako budoucí centrální evidence zaměstnanců.

    Osobní číslo je jedinečné jen tehdy, když je vyplněné. NULL a prázdný text
    jedinečnost neobsazují, aby šlo později přenést čísla z test_employees,
    aniž by se prázdné řádky THP navzájem blokovaly. Sám převod tato tabulka nedělá.
    Textová funkce ``position`` a číselníkové role v ``thp_worker_roles`` jsou
    dva nezávislé údaje. Výslovné propojení s ``test_employees`` je v tabulce
    ``test_employee_central_links``. Podle jména ani osobního čísla se
    záznamy samy nespojují.
    """

    __tablename__ = "thp_workers"
    __table_args__ = (
        Index(
            "uq_thp_workers_personal_number",
            "personal_number",
            unique=True,
            sqlite_where=text(
                "personal_number IS NOT NULL AND personal_number <> ''"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title_before: Mapped[str] = mapped_column(String(50), default="")
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title_after: Mapped[str] = mapped_column(String(50), default="")

    position: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")

    # Nevyplněné osobní číslo je NULL. Prázdný řetězec je také povolený
    # a do jedinečného indexu nevstupuje.
    personal_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workplace_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("workplaces.id"),
        nullable=True,
    )
    is_thp: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    may_examine: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    performs_controls: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=datetime.now,
        onupdate=datetime.now,
    )

    @property
    def full_name(self) -> str:
        base = " ".join(
            part for part in [
                self.title_before,
                self.first_name,
                self.last_name,
            ]
            if part
        ).strip()

        if self.title_after:
            return f"{base}, {self.title_after}".strip()

        return base

    @property
    def display_name(self) -> str:
        return self.full_name
