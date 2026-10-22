"""Výslovné propojení zaměstnance z Testů na centrální evidenci (EMPLOYEE-CENTRAL-3).

Řádek vznikne jen voláním služby. Migrace ani shoda jména nebo osobního
čísla sem nic nevkládá. Jeden zaměstnanec z Testů míří nejvýše na jednoho
centrálního zaměstnance a naopak.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class TestEmployeeCentralLink(Base):
    __tablename__ = "test_employee_central_links"
    __table_args__ = (
        UniqueConstraint(
            "test_employee_id",
            name="uq_test_employee_central_links_employee",
        ),
        UniqueConstraint(
            "thp_worker_id",
            name="uq_test_employee_central_links_worker",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_employees.id"),
        nullable=False,
    )
    thp_worker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("thp_workers.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
