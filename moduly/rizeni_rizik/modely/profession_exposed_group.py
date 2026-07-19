"""M:N vazba profese ↔ ohrožená skupina (PBP-5c)."""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class ProfessionExposedGroup(Base):
    """Vazba profese na ohrožené skupiny osob."""

    __tablename__ = "profession_exposed_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profession_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    exposed_group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
