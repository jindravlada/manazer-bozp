from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource


class LegalRequirementSourceRepository:
    def list_all(self) -> list[LegalRequirementSource]:
        with get_session() as session:
            stmt = select(LegalRequirementSource).order_by(
                LegalRequirementSource.requirement_id,
                LegalRequirementSource.sort_order,
                LegalRequirementSource.id,
            )
            return list(session.scalars(stmt))

    def list_for_active_requirements(self) -> list[LegalRequirementSource]:
        with get_session() as session:
            stmt = (
                select(LegalRequirementSource)
                .join(
                    LegalRequirement,
                    LegalRequirement.id == LegalRequirementSource.requirement_id,
                )
                .where(LegalRequirement.active.is_(True))
                .order_by(
                    LegalRequirementSource.requirement_id,
                    LegalRequirementSource.sort_order,
                    LegalRequirementSource.id,
                )
            )
            return list(session.scalars(stmt))

    def list_by_requirement(self, requirement_id: int) -> list[LegalRequirementSource]:
        with get_session() as session:
            stmt = (
                select(LegalRequirementSource)
                .where(LegalRequirementSource.requirement_id == requirement_id)
                .order_by(LegalRequirementSource.sort_order, LegalRequirementSource.id)
            )
            return list(session.scalars(stmt))

    def list_section_ids_by_requirement(self, requirement_id: int) -> list[int]:
        return [
            source.legal_section_id
            for source in self.list_by_requirement(requirement_id)
        ]

    def list_by_section_ids(self, section_ids: list[int]) -> list[LegalRequirementSource]:
        if not section_ids:
            return []
        with get_session() as session:
            stmt = (
                select(LegalRequirementSource)
                .where(LegalRequirementSource.legal_section_id.in_(section_ids))
                .order_by(
                    LegalRequirementSource.legal_section_id,
                    LegalRequirementSource.requirement_id,
                    LegalRequirementSource.sort_order,
                    LegalRequirementSource.id,
                )
            )
            return list(session.scalars(stmt))

    def list_linked_section_ids(self, *, section_ids: list[int] | None = None) -> set[int]:
        with get_session() as session:
            stmt = select(LegalRequirementSource.legal_section_id)
            if section_ids:
                stmt = stmt.where(LegalRequirementSource.legal_section_id.in_(section_ids))
            return {value for value in session.scalars(stmt) if value is not None}

    def get_first_requirement_id_by_section(self, section_id: int) -> int | None:
        with get_session() as session:
            stmt = (
                select(LegalRequirementSource.requirement_id)
                .join(
                    LegalRequirement,
                    LegalRequirement.id == LegalRequirementSource.requirement_id,
                )
                .where(LegalRequirementSource.legal_section_id == section_id)
                .where(LegalRequirement.active.is_(True))
                .order_by(
                    LegalRequirementSource.sort_order,
                    LegalRequirementSource.id,
                )
            )
            return session.scalars(stmt).first()

    def has_section(self, section_id: int) -> bool:
        with get_session() as session:
            stmt = (
                select(LegalRequirementSource.id)
                .where(LegalRequirementSource.legal_section_id == section_id)
                .limit(1)
            )
            return session.scalars(stmt).first() is not None

    def create(self, source: LegalRequirementSource) -> LegalRequirementSource:
        with get_session() as session:
            session.add(source)
            session.commit()
            session.refresh(source)
            return source

    def delete(self, source_id: int) -> None:
        with get_session() as session:
            source = session.get(LegalRequirementSource, source_id)
            if source is not None:
                session.delete(source)
                session.commit()

    def delete_by_requirement(self, requirement_id: int) -> None:
        with get_session() as session:
            stmt = select(LegalRequirementSource).where(
                LegalRequirementSource.requirement_id == requirement_id,
            )
            for source in session.scalars(stmt):
                session.delete(source)
            session.commit()

    def replace_for_requirement(
        self,
        requirement_id: int,
        section_ids: list[int],
    ) -> list[LegalRequirementSource]:
        unique_section_ids: list[int] = []
        seen: set[int] = set()
        for section_id in section_ids:
            if section_id in seen:
                continue
            seen.add(section_id)
            unique_section_ids.append(section_id)

        self.delete_by_requirement(requirement_id)
        created: list[LegalRequirementSource] = []
        for index, section_id in enumerate(unique_section_ids, start=1):
            created.append(
                self.create(
                    LegalRequirementSource(
                        requirement_id=requirement_id,
                        legal_section_id=section_id,
                        sort_order=index,
                    ),
                ),
            )
        return created
