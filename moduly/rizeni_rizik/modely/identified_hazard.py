from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.constants import DEFAULT_IDENTIFIED_HAZARD_SOURCE


class IdentifiedHazard(Base):
    __tablename__ = "identified_hazards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_identification_id: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    @staticmethod
    def default_source_type() -> str:
        return DEFAULT_IDENTIFIED_HAZARD_SOURCE
