from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_section import LegalSection


class LegalSectionRepository:
    def list_by_document(
        self,
        document_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalSection]:
        with get_session() as session:
            stmt = (
                select(LegalSection)
                .where(LegalSection.legal_document_id == document_id)
                .order_by(LegalSection.sort_order, LegalSection.id)
            )
            if not include_inactive:
                stmt = stmt.where(LegalSection.active.is_(True))
            return list(session.scalars(stmt))

    def list_by_version(
        self,
        version_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalSection]:
        with get_session() as session:
            stmt = (
                select(LegalSection)
                .where(LegalSection.legal_document_version_id == version_id)
                .order_by(LegalSection.sort_order, LegalSection.id)
            )
            if not include_inactive:
                stmt = stmt.where(LegalSection.active.is_(True))
            return list(session.scalars(stmt))

    def list_children(
        self,
        parent_section_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalSection]:
        with get_session() as session:
            stmt = (
                select(LegalSection)
                .where(LegalSection.parent_section_id == parent_section_id)
                .order_by(LegalSection.sort_order, LegalSection.id)
            )
            if not include_inactive:
                stmt = stmt.where(LegalSection.active.is_(True))
            return list(session.scalars(stmt))

    def list_active(
        self,
        *,
        document_id: int | None = None,
    ) -> list[LegalSection]:
        with get_session() as session:
            stmt = (
                select(LegalSection)
                .where(LegalSection.active.is_(True))
                .order_by(LegalSection.sort_order, LegalSection.id)
            )
            if document_id is not None:
                stmt = stmt.where(LegalSection.legal_document_id == document_id)
            return list(session.scalars(stmt))

    def get_by_id(self, section_id: int) -> LegalSection | None:
        with get_session() as session:
            return session.get(LegalSection, section_id)

    def create(self, section: LegalSection) -> LegalSection:
        with get_session() as session:
            session.add(section)
            session.commit()
            session.refresh(section)
            return section

    def update(self, section: LegalSection) -> LegalSection:
        with get_session() as session:
            section = session.merge(section)
            session.commit()
            session.refresh(section)
            return section

    def deactivate(self, section_id: int) -> LegalSection | None:
        section = self.get_by_id(section_id)
        if section is None:
            return None
        section.active = False
        return self.update(section)

    def restore(self, section_id: int) -> LegalSection | None:
        section = self.get_by_id(section_id)
        if section is None:
            return None
        section.active = True
        return self.update(section)
