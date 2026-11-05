"""Odkaz koordinace na konkrétní dokument katalogu rizik dodavatele.

Soubor se nekopíruje. Stejný dokument lze u jednoho dodavatele použít jen jednou.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class CoordinationSupplierRiskLink(Base):
    """Potvrzené použití dokumentu z katalogu u dodavatele v koordinaci."""

    __tablename__ = "coordination_supplier_risk_links"
    __table_args__ = (
        UniqueConstraint(
            "coordination_employer_id",
            "supplier_risk_document_id",
            name="uq_coordination_supplier_risk_links_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_risk_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_risk_documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
