from sqlalchemy import func, select

from core.database.session import get_session
from moduly.tymy.modely.team import Team


class TeamRepository:
    def get_all(self) -> list[Team]:
        with get_session() as session:
            stmt = select(Team).order_by(Team.name, Team.id)
            return list(session.scalars(stmt))

    def get_active(self) -> list[Team]:
        with get_session() as session:
            stmt = (
                select(Team)
                .where(Team.active.is_(True))
                .order_by(Team.name, Team.id)
            )
            return list(session.scalars(stmt))

    def get_by_id(self, team_id: int) -> Team | None:
        with get_session() as session:
            return session.get(Team, team_id)

    def add(self, team: Team) -> Team:
        with get_session() as session:
            session.add(team)
            session.commit()
            session.refresh(team)
            return team

    def update(self, team: Team) -> Team:
        with get_session() as session:
            team = session.merge(team)
            session.commit()
            session.refresh(team)
            return team

    def delete(self, team_id: int) -> bool:
        with get_session() as session:
            team = session.get(Team, team_id)
            if team is None:
                return False

            session.delete(team)
            session.commit()
            return True
