from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class HazardInventoryRelation(Base):
    __tablename__ = "hazard_inventory_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_identification_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
