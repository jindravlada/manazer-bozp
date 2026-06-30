from sqlalchemy import select

from core.database.session import get_session
from moduly.vysetrovani_mu.modely.mu_investigation import MuInvestigation


class MuInvestigationRepository:
    def get_all(self) -> list[MuInvestigation]:
        with get_session() as session:
            stmt = select(MuInvestigation).order_by(
                MuInvestigation.started_at.desc(),
                MuInvestigation.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, investigation_id: int) -> MuInvestigation | None:
        with get_session() as session:
            return session.get(MuInvestigation, investigation_id)

    def find_by_source(self, source_type: str, source_id: int) -> MuInvestigation | None:
        with get_session() as session:
            stmt = (
                select(MuInvestigation)
                .where(
                    MuInvestigation.source_type == source_type,
                    MuInvestigation.source_id == source_id,
                )
                .order_by(MuInvestigation.id.desc())
            )
            return session.scalars(stmt).first()

    def add(self, investigation: MuInvestigation) -> MuInvestigation:
        with get_session() as session:
            session.add(investigation)
            session.commit()
            session.refresh(investigation)
            return investigation

    def update(self, investigation: MuInvestigation) -> MuInvestigation:
        with get_session() as session:
            investigation = session.merge(investigation)
            session.commit()
            session.refresh(investigation)
            return investigation

    def delete(self, investigation_id: int) -> bool:
        with get_session() as session:
            investigation = session.get(MuInvestigation, investigation_id)
            if investigation is None:
                return False

            session.delete(investigation)
            session.commit()
            return True
