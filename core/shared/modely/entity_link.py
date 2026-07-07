from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.shared.constants import LINK_RELATED


class EntityLink(Base):
    """Univerzální vazba mezi objekty napříč moduly."""

    __tablename__ = "entity_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)

    link_type: Mapped[str] = mapped_column(String(50), default=LINK_RELATED)
    note: Mapped[str] = mapped_column(Text, default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
