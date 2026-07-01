from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.shared.constants import CONTROL_RESULT_NEKONTROLOVANO


class ControlResult(Base):
    """
    Výsledek kontroly kontrolního bodu navázaný na hlavní záznam modulu.

    Společná entita pro Prověrky BOZP, Audity a budoucí modul Kontroly.
    """

    __tablename__ = "control_results"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "source_area_label",
            "source_section_label",
            "source_control_point_id",
            name="uq_control_results_control_point",
        ),
        Index("ix_control_results_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    source_area_id: Mapped[str] = mapped_column(String(80), default="")
    source_area_label: Mapped[str] = mapped_column(String(150), default="")
    source_section_id: Mapped[str] = mapped_column(String(80), default="")
    source_section_label: Mapped[str] = mapped_column(String(150), default="")
    source_control_point_id: Mapped[str] = mapped_column(String(80), default="")
    source_control_point_label: Mapped[str] = mapped_column(String(200), default="")

    result: Mapped[str] = mapped_column(
        String(40),
        default=CONTROL_RESULT_NEKONTROLOVANO,
        nullable=False,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    shared_experience: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    photo_path: Mapped[str] = mapped_column(String(500), default="")

    recorded_by_name: Mapped[str] = mapped_column(String(150), default="")
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
