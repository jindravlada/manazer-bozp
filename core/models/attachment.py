from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Attachment(Base):
    """
    Globální příloha k libovolnému záznamu.

    entity_type:
      task
      accident
      audit
      inspection
      review
      ...
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    original_path: Mapped[str] = mapped_column(String(500), default="")
    stored_path: Mapped[str] = mapped_column(String(500), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
