"""Vazba zaměstnance na funkce / role (TESTY-2a)."""

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestEmployeeRole(Base):
    """Odkaz na číselník Funkce / role. Název role se sem nekopíruje."""

    __tablename__ = "test_employee_roles"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "responsibility_role_id",
            name="uq_test_employee_roles_employee_role",
        ),
        Index("ix_test_employee_roles_employee_id", "employee_id"),
        Index(
            "ix_test_employee_roles_responsibility_role_id",
            "responsibility_role_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_employees.id"),
        nullable=False,
    )
    responsibility_role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("responsibility_roles.id"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
