from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from core.models.attachment import Attachment
from moduly.rizeni_rizik.modely.supplier_risk import (
    SupplierRiskCompany,
    SupplierRiskDocument,
)


class SupplierRiskRepository:
    def list_companies(self) -> list[SupplierRiskCompany]:
        with get_session() as session:
            stmt = select(SupplierRiskCompany).order_by(
                SupplierRiskCompany.name,
                SupplierRiskCompany.id,
            )
            companies = list(session.scalars(stmt))
            for company in companies:
                session.expunge(company)
            return companies

    def get_company(self, company_id: int) -> SupplierRiskCompany | None:
        with get_session() as session:
            company = session.get(SupplierRiskCompany, company_id)
            if company is not None:
                session.expunge(company)
            return company

    def get_by_ico(self, ico: str) -> SupplierRiskCompany | None:
        with get_session() as session:
            stmt = select(SupplierRiskCompany).where(SupplierRiskCompany.ico == ico)
            company = session.scalars(stmt).first()
            if company is not None:
                session.expunge(company)
            return company

    def add_company(self, company: SupplierRiskCompany) -> SupplierRiskCompany:
        with get_session() as session:
            session.add(company)
            session.commit()
            session.refresh(company)
            session.expunge(company)
            return company

    def update_company(self, company: SupplierRiskCompany) -> SupplierRiskCompany:
        with get_session() as session:
            company.updated_at = datetime.now()
            merged = session.merge(company)
            session.commit()
            session.refresh(merged)
            session.expunge(merged)
            return merged

    def add_document(self, document: SupplierRiskDocument) -> SupplierRiskDocument:
        with get_session() as session:
            session.add(document)
            session.commit()
            session.refresh(document)
            session.expunge(document)
            return document

    def update_document(self, document: SupplierRiskDocument) -> SupplierRiskDocument:
        with get_session() as session:
            document.updated_at = datetime.now()
            merged = session.merge(document)
            session.commit()
            session.refresh(merged)
            session.expunge(merged)
            return merged

    def get_by_coordination_attachment(
        self,
        coordination_attachment_id: int,
    ) -> SupplierRiskDocument | None:
        with get_session() as session:
            stmt = select(SupplierRiskDocument).where(
                SupplierRiskDocument.coordination_attachment_id
                == coordination_attachment_id
            )
            document = session.scalars(stmt).first()
            if document is not None:
                session.expunge(document)
            return document

    def delete_company_without_documents(self, company_id: int) -> None:
        """Smaže firmu jen tehdy, když u ní není žádný dokument."""
        with get_session() as session:
            company = session.get(SupplierRiskCompany, company_id)
            if company is None:
                return
            document_id = session.scalar(
                select(SupplierRiskDocument.id)
                .where(SupplierRiskDocument.company_id == company_id)
                .limit(1)
            )
            if document_id is not None:
                return
            session.delete(company)
            session.commit()

    def get_document(self, document_id: int) -> SupplierRiskDocument | None:
        with get_session() as session:
            document = session.get(SupplierRiskDocument, document_id)
            if document is not None:
                session.expunge(document)
            return document

    def delete_document(self, document_id: int) -> None:
        with get_session() as session:
            document = session.get(SupplierRiskDocument, document_id)
            if document is None:
                return
            session.delete(document)
            session.commit()

    def list_rows(self) -> list[tuple[SupplierRiskDocument, SupplierRiskCompany, Attachment | None]]:
        with get_session() as session:
            stmt = (
                select(SupplierRiskDocument, SupplierRiskCompany, Attachment)
                .join(
                    SupplierRiskCompany,
                    SupplierRiskCompany.id == SupplierRiskDocument.company_id,
                )
                .outerjoin(Attachment, Attachment.id == SupplierRiskDocument.attachment_id)
                .order_by(SupplierRiskCompany.name, SupplierRiskDocument.id)
            )
            rows = list(session.execute(stmt))
            seen: set[tuple[type, int]] = set()
            for document, company, attachment in rows:
                for obj in (document, company, attachment):
                    if obj is None or obj.id is None:
                        continue
                    key = (type(obj), int(obj.id))
                    if key in seen:
                        continue
                    seen.add(key)
                    session.expunge(obj)
            return rows
