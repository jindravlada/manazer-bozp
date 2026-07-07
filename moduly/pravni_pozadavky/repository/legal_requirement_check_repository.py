from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_requirement_check import LegalRequirementCheck


class LegalRequirementCheckRepository:
    def get_by_requirement_id(self, requirement_id: int) -> list[LegalRequirementCheck]:
        with get_session() as session:
            stmt = (
                select(LegalRequirementCheck)
                .where(LegalRequirementCheck.legal_requirement_id == requirement_id)
                .order_by(LegalRequirementCheck.check_date.desc(), LegalRequirementCheck.id.desc())
            )
            return list(session.scalars(stmt))

    def add(self, check: LegalRequirementCheck) -> LegalRequirementCheck:
        with get_session() as session:
            session.add(check)
            session.commit()
            session.refresh(check)
            return check
