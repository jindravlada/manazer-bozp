from sqlalchemy import select

from core.database.session import get_session
from moduly.kniha_urazu.modely.investigation import AccidentInvestigation


class InvestigationRepository:
    def get_by_accident_id(self, accident_id: int) -> AccidentInvestigation | None:
        with get_session() as session:
            stmt = select(AccidentInvestigation).where(AccidentInvestigation.accident_id == accident_id)
            return session.scalars(stmt).first()

    def save(self, investigation: AccidentInvestigation) -> AccidentInvestigation:
        with get_session() as session:
            investigation = session.merge(investigation)
            session.commit()
            session.refresh(investigation)
            return investigation
