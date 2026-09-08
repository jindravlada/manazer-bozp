from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion


class LegalDocumentVersionRepository:
    def list_all(self, *, include_inactive: bool = False) -> list[LegalDocumentVersion]:
        with get_session() as session:
            stmt = select(LegalDocumentVersion).order_by(
                LegalDocumentVersion.legal_document_id,
                LegalDocumentVersion.active.desc(),
                LegalDocumentVersion.effective_from.desc(),
                LegalDocumentVersion.id,
            )
            if not include_inactive:
                stmt = stmt.where(LegalDocumentVersion.active.is_(True))
            return list(session.scalars(stmt))

    def list_by_document(
        self,
        document_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalDocumentVersion]:
        with get_session() as session:
            stmt = (
                select(LegalDocumentVersion)
                .where(LegalDocumentVersion.legal_document_id == document_id)
                .order_by(
                    LegalDocumentVersion.active.desc(),
                    LegalDocumentVersion.effective_from.desc(),
                    LegalDocumentVersion.id.desc(),
                )
            )
            if not include_inactive:
                stmt = stmt.where(LegalDocumentVersion.active.is_(True))
            return list(session.scalars(stmt))

    def find_pending_by_checksum(
        self,
        document_id: int,
        checksum: str,
    ) -> LegalDocumentVersion | None:
        normalized = (checksum or "").strip()
        if not normalized:
            return None
        with get_session() as session:
            stmt = (
                select(LegalDocumentVersion)
                .where(
                    LegalDocumentVersion.legal_document_id == document_id,
                    LegalDocumentVersion.checksum == normalized,
                    LegalDocumentVersion.pending_adoption.is_(True),
                )
                .order_by(LegalDocumentVersion.id.asc())
            )
            return session.scalar(stmt)

    def get_by_id(self, version_id: int) -> LegalDocumentVersion | None:
        with get_session() as session:
            return session.get(LegalDocumentVersion, version_id)

    def create(self, version: LegalDocumentVersion) -> LegalDocumentVersion:
        with get_session() as session:
            session.add(version)
            session.commit()
            session.refresh(version)
            return version

    def update(self, version: LegalDocumentVersion) -> LegalDocumentVersion:
        with get_session() as session:
            version = session.merge(version)
            session.commit()
            session.refresh(version)
            return version
