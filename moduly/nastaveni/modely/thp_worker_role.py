"""Vazba pracovníka na více funkcí / rolí (EMPLOYEE-CENTRAL-1).

Stejný princip jako ``test_employee_roles``: odkaz na číselník
``responsibility_roles``, název role se sem nekopíruje.
Textové pole ``thp_workers.position`` zůstává samostatný údaj.
"""

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class ThpWorkerRole(Base):
    __tablename__ = "thp_worker_roles"
    __table_args__ = (
        UniqueConstraint(
            "thp_worker_id",
            "responsibility_role_id",
            name="uq_thp_worker_roles_worker_role",
        ),
        Index("ix_thp_worker_roles_thp_worker_id", "thp_worker_id"),
        Index(
            "ix_thp_worker_roles_responsibility_role_id",
            "responsibility_role_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thp_worker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("thp_workers.id"),
        nullable=False,
    )
    responsibility_role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("responsibility_roles.id"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
