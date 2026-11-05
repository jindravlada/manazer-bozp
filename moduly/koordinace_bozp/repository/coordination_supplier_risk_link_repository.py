"""Úložiště odkazů koordinace na dokumenty katalogu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from core.database.session import get_session
from core.models.attachment import Attachment
from moduly.koordinace_bozp.modely.coordination_attachment import CoordinationAttachment
from moduly.koordinace_bozp.modely.coordination_supplier_risk_link import (
    CoordinationSupplierRiskLink,
)
from moduly.rizeni_rizik.modely.supplier_risk import SupplierRiskDocument


@dataclass(frozen=True)
class StoredCatalogLink:
    link_id: int
    coordination_employer_id: int
    document_id: int
    filename: str
    prepared_on: date | None
    received_on: date | None


class CoordinationSupplierRiskLinkRepository:
    def list_for_employer(self, coordination_employer_id: int) -> list[StoredCatalogLink]:
        with get_session() as session:
            stmt = (
                select(
                    CoordinationSupplierRiskLink.id,
                    CoordinationSupplierRiskLink.coordination_employer_id,
                    CoordinationSupplierRiskLink.supplier_risk_document_id,
                    SupplierRiskDocument.prepared_on,
                    SupplierRiskDocument.received_on,
                    func.coalesce(
                        Attachment.filename,
                        CoordinationAttachment.original_filename,
                    ),
                )
                .join(
                    SupplierRiskDocument,
                    SupplierRiskDocument.id
                    == CoordinationSupplierRiskLink.supplier_risk_document_id,
                )
                .outerjoin(
                    Attachment,
                    Attachment.id == SupplierRiskDocument.attachment_id,
                )
                .outerjoin(
                    CoordinationAttachment,
                    CoordinationAttachment.id
                    == SupplierRiskDocument.coordination_attachment_id,
                )
                .where(
                    CoordinationSupplierRiskLink.coordination_employer_id
                    == coordination_employer_id
                )
                .order_by(CoordinationSupplierRiskLink.id)
            )
            return [
                StoredCatalogLink(
                    link_id=int(link_id),
                    coordination_employer_id=int(employer_id),
                    document_id=int(document_id),
                    filename=(filename or "").strip(),
                    prepared_on=prepared_on,
                    received_on=received_on,
                )
                for (
                    link_id,
                    employer_id,
                    document_id,
                    prepared_on,
                    received_on,
                    filename,
                ) in session.execute(stmt)
            ]

    def add(
        self,
        *,
        coordination_employer_id: int,
        supplier_risk_document_id: int,
    ) -> None:
        with get_session() as session:
            session.add(
                CoordinationSupplierRiskLink(
                    coordination_employer_id=coordination_employer_id,
                    supplier_risk_document_id=supplier_risk_document_id,
                    created_at=datetime.now(),
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise

    def delete_for_employer(
        self,
        coordination_employer_id: int,
        document_ids: list[int],
    ) -> None:
        if not document_ids:
            return
        with get_session() as session:
            session.execute(
                delete(CoordinationSupplierRiskLink).where(
                    CoordinationSupplierRiskLink.coordination_employer_id
                    == coordination_employer_id,
                    CoordinationSupplierRiskLink.supplier_risk_document_id.in_(
                        document_ids
                    ),
                )
            )
            session.commit()
