from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Meeting(Base):
    """Samostatná evidence schůzky (není úkol)."""

    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(250), default="", nullable=False)

    event_type: Mapped[str] = mapped_column(String(100), default="Schůzka", nullable=False)

    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    location: Mapped[str] = mapped_column(String(250), default="")

    organizer_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    organizer_name: Mapped[str] = mapped_column(String(200), default="")

    participant_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    participant_names: Mapped[str] = mapped_column(Text, default="")

    agenda: Mapped[str] = mapped_column(Text, default="")

    # Záznam z jednání (volitelné)
    proceedings: Mapped[str] = mapped_column(Text, default="")
    conclusions: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(30), default="Naplánováno", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
