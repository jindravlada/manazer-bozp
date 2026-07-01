from sqlalchemy import func, select

from core.database.session import get_session
from moduly.tymy.modely.team_member import TeamMember


class TeamMemberRepository:
    def get_for_team(self, team_id: int) -> list[TeamMember]:
        with get_session() as session:
            stmt = (
                select(TeamMember)
                .where(TeamMember.team_id == team_id)
                .order_by(TeamMember.display_order, TeamMember.id)
            )
            return list(session.scalars(stmt))

    def get_by_id(self, member_id: int) -> TeamMember | None:
        with get_session() as session:
            return session.get(TeamMember, member_id)

    def add(self, member: TeamMember) -> TeamMember:
        with get_session() as session:
            session.add(member)
            session.commit()
            session.refresh(member)
            return member

    def update(self, member: TeamMember) -> TeamMember:
        with get_session() as session:
            member = session.merge(member)
            session.commit()
            session.refresh(member)
            return member

    def delete(self, member_id: int) -> bool:
        with get_session() as session:
            member = session.get(TeamMember, member_id)
            if member is None:
                return False

            session.delete(member)
            session.commit()
            return True

    def delete_for_team(self, team_id: int) -> int:
        with get_session() as session:
            stmt = select(TeamMember).where(TeamMember.team_id == team_id)
            members = list(session.scalars(stmt))
            for member in members:
                session.delete(member)
            session.commit()
            return len(members)

    def max_display_order(self, team_id: int) -> int:
        with get_session() as session:
            stmt = select(func.max(TeamMember.display_order)).where(
                TeamMember.team_id == team_id,
            )
            value = session.scalar(stmt)
            return int(value or 0)
