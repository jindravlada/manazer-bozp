from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.shared.constants import FINDING_STATUS_OTEVRENE, FINDING_TYPE_ZJISTENI


class Finding(Base):
    """
    Sdílené zjištění navázané na hlavní záznam modulu.

    Budoucí rozšíření:
    - přílohy/fotografie: Attachment(entity_type=ENTITY_FINDING, entity_id=id)
    - komentáře a historie: samostatné entity s vazbou na ENTITY_FINDING
    - úkol: task_id + modul Úkoly (fáze 2)
    """

    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_entity", "entity_type", "entity_id"),
        Index("ix_findings_task_id", "task_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    finding_type: Mapped[str] = mapped_column(String(30), default=FINDING_TYPE_ZJISTENI, nullable=False)
    reference_label: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")

    recommended_action: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    responsible_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsible_person_name: Mapped[str] = mapped_column(String(150), default="")

    status: Mapped[str] = mapped_column(String(30), default=FINDING_STATUS_OTEVRENE, nullable=False)
    resolved_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="")

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
