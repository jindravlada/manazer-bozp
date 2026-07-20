from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
from moduly.koordinace_bozp.modely.coordination_employer_activity import (
    CoordinationEmployerActivity,
)


class CoordinationEmployerActivityRepository:
    def list_for_employer(
        self,
        coordination_employer_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationEmployerActivity]:
        with get_session() as session:
            stmt = select(CoordinationEmployerActivity).where(
                CoordinationEmployerActivity.coordination_employer_id
                == coordination_employer_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationEmployerActivity.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationEmployerActivity.sort_order,
                CoordinationEmployerActivity.activity_name,
                CoordinationEmployerActivity.id,
            )
            return list(session.scalars(stmt))

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationEmployerActivity]:
        with get_session() as session:
            stmt = (
                select(CoordinationEmployerActivity)
                .join(
                    CoordinationEmployer,
                    CoordinationEmployer.id
                    == CoordinationEmployerActivity.coordination_employer_id,
                )
                .where(CoordinationEmployer.coordination_id == coordination_id)
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationEmployerActivity.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationEmployer.sort_order,
                CoordinationEmployer.company_name,
                CoordinationEmployer.id,
                CoordinationEmployerActivity.planned_from,
                CoordinationEmployerActivity.activity_name,
                CoordinationEmployerActivity.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, activity_id: int) -> CoordinationEmployerActivity | None:
        with get_session() as session:
            return session.get(CoordinationEmployerActivity, activity_id)

    def add(
        self,
        activity: CoordinationEmployerActivity,
    ) -> CoordinationEmployerActivity:
        with get_session() as session:
            session.add(activity)
            session.commit()
            session.refresh(activity)
            return activity

    def update(
        self,
        activity: CoordinationEmployerActivity,
    ) -> CoordinationEmployerActivity:
        with get_session() as session:
            activity = session.merge(activity)
            session.commit()
            session.refresh(activity)
            return activity

    def next_sort_order(self, coordination_employer_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationEmployerActivity.sort_order)
                .where(
                    CoordinationEmployerActivity.coordination_employer_id
                    == coordination_employer_id,
                )
                .order_by(CoordinationEmployerActivity.sort_order.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1
