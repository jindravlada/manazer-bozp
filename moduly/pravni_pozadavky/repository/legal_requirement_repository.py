from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement


class LegalRequirementRepository:
    def get_all(self, *, active_only: bool | None = None) -> list[LegalRequirement]:
        with get_session() as session:
            stmt = select(LegalRequirement).order_by(
                LegalRequirement.active.desc(),
                LegalRequirement.next_verification_date,
                LegalRequirement.regulation_name,
                LegalRequirement.id,
            )
            if active_only is True:
                stmt = stmt.where(LegalRequirement.active.is_(True))
            elif active_only is False:
                stmt = stmt.where(LegalRequirement.active.is_(False))
            return list(session.scalars(stmt))

    def get_by_id(self, requirement_id: int) -> LegalRequirement | None:
        with get_session() as session:
            return session.get(LegalRequirement, requirement_id)

    def list_source_section_ids(self, *, section_ids: list[int] | None = None) -> set[int]:
        with get_session() as session:
            stmt = select(LegalRequirement.source_section_id).where(
                LegalRequirement.source_section_id.is_not(None),
            )
            if section_ids:
                stmt = stmt.where(LegalRequirement.source_section_id.in_(section_ids))
            return {value for value in session.scalars(stmt) if value is not None}

    def get_by_source_section_id(self, section_id: int) -> LegalRequirement | None:
        with get_session() as session:
            stmt = (
                select(LegalRequirement)
                .where(LegalRequirement.source_section_id == section_id)
                .order_by(
                    LegalRequirement.active.desc(),
                    LegalRequirement.id.desc(),
                )
            )
            return session.scalars(stmt).first()

    def list_by_source_section_ids(self, section_ids: list[int]) -> list[LegalRequirement]:
        if not section_ids:
            return []
        with get_session() as session:
            stmt = (
                select(LegalRequirement)
                .where(LegalRequirement.source_section_id.in_(section_ids))
                .order_by(
                    LegalRequirement.source_section_id,
                    LegalRequirement.active.desc(),
                    LegalRequirement.id.desc(),
                )
            )
            return list(session.scalars(stmt))

    def add(self, requirement: LegalRequirement) -> LegalRequirement:
        with get_session() as session:
            session.add(requirement)
            session.commit()
            session.refresh(requirement)
            return requirement

    def update(self, requirement: LegalRequirement) -> LegalRequirement:
        with get_session() as session:
            requirement = session.merge(requirement)
            session.commit()
            session.refresh(requirement)
            return requirement
