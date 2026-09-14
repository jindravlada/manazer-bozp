from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class LegalDocumentVersion(Base):
    """Verze právního předpisu."""

    __tablename__ = "legal_document_versions"
    __table_args__ = (
        UniqueConstraint(
            "legal_document_id",
            "source_eli",
            name="uq_legal_document_versions_document_source_eli",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_document_id: Mapped[int] = mapped_column(Integer, nullable=False)

    version_name: Mapped[str] = mapped_column(String(150), nullable=False)

    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    source_eli: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500), default="")
    local_file_path: Mapped[str] = mapped_column(String(500), default="")
    checksum: Mapped[str] = mapped_column(String(128), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    pending_adoption: Mapped[bool] = mapped_column(Boolean, default=False)
    future_wording: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
