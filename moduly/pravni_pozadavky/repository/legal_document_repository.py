from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument


class LegalDocumentRepository:
    def list_all(self, *, include_inactive: bool = False) -> list[LegalDocument]:
        with get_session() as session:
            stmt = select(LegalDocument).order_by(
                LegalDocument.active.desc(),
                LegalDocument.year.desc(),
                LegalDocument.title,
                LegalDocument.id,
            )
            if not include_inactive:
                stmt = stmt.where(LegalDocument.active.is_(True))
            return list(session.scalars(stmt))

    def get_by_id(self, document_id: int) -> LegalDocument | None:
        with get_session() as session:
            return session.get(LegalDocument, document_id)

    def create(self, document: LegalDocument) -> LegalDocument:
        with get_session() as session:
            session.add(document)
            session.commit()
            session.refresh(document)
            return document

    def update(self, document: LegalDocument) -> LegalDocument:
        with get_session() as session:
            document = session.merge(document)
            session.commit()
            session.refresh(document)
            return document
