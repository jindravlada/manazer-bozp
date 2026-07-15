from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class HazardLibraryTemplateRevision(Base):
    """Historie revizí odborného obsahu zdroje rizika (R18g.1).

    Pole author, changed_objects_json a comment jsou připravena pro budoucí rozšíření.
    """

    __tablename__ = "hazard_library_template_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    change_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    changed_objects_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
