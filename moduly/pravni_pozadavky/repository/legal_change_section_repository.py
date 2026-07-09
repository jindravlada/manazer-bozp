from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection


class LegalChangeSectionRepository:
    def list_all(self) -> list[LegalChangeSection]:
        with get_session() as session:
            stmt = select(LegalChangeSection).order_by(
                LegalChangeSection.legal_change_id,
                LegalChangeSection.id,
            )
            return list(session.scalars(stmt))

    def list_by_change(self, legal_change_id: int) -> list[LegalChangeSection]:
        with get_session() as session:
            stmt = (
                select(LegalChangeSection)
                .where(LegalChangeSection.legal_change_id == legal_change_id)
                .order_by(
                    LegalChangeSection.change_type,
                    LegalChangeSection.section_label,
                    LegalChangeSection.id,
                )
            )
            return list(session.scalars(stmt))

    def create(self, section: LegalChangeSection) -> LegalChangeSection:
        with get_session() as session:
            session.add(section)
            session.commit()
            session.refresh(section)
            return section

    def create_many(self, sections: list[LegalChangeSection]) -> list[LegalChangeSection]:
        if not sections:
            return []
        with get_session() as session:
            session.add_all(sections)
            session.commit()
            for section in sections:
                session.refresh(section)
            return sections
