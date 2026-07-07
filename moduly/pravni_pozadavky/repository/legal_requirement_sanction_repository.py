from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_requirement_sanction import LegalRequirementSanction


class LegalRequirementSanctionRepository:
    def list_by_requirement(
        self,
        requirement_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalRequirementSanction]:
        with get_session() as session:
            stmt = (
                select(LegalRequirementSanction)
                .where(LegalRequirementSanction.requirement_id == requirement_id)
                .order_by(
                    LegalRequirementSanction.active.desc(),
                    LegalRequirementSanction.id,
                )
            )
            if not include_inactive:
                stmt = stmt.where(LegalRequirementSanction.active.is_(True))
            return list(session.scalars(stmt))

    def get_by_id(self, sanction_id: int) -> LegalRequirementSanction | None:
        with get_session() as session:
            return session.get(LegalRequirementSanction, sanction_id)

    def create(self, sanction: LegalRequirementSanction) -> LegalRequirementSanction:
        with get_session() as session:
            session.add(sanction)
            session.commit()
            session.refresh(sanction)
            return sanction

    def update(self, sanction: LegalRequirementSanction) -> LegalRequirementSanction:
        with get_session() as session:
            sanction = session.merge(sanction)
            session.commit()
            session.refresh(sanction)
            return sanction
