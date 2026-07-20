from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure


class CoordinationMeasureRepository:
    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationMeasure]:
        with get_session() as session:
            stmt = select(CoordinationMeasure).where(
                CoordinationMeasure.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationMeasure.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationMeasure.sort_order,
                CoordinationMeasure.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, measure_id: int) -> CoordinationMeasure | None:
        with get_session() as session:
            return session.get(CoordinationMeasure, measure_id)

    def add(self, measure: CoordinationMeasure) -> CoordinationMeasure:
        with get_session() as session:
            session.add(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def update(self, measure: CoordinationMeasure) -> CoordinationMeasure:
        with get_session() as session:
            measure = session.merge(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def next_sort_order(self, coordination_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationMeasure.sort_order)
                .where(CoordinationMeasure.coordination_id == coordination_id)
                .order_by(CoordinationMeasure.sort_order.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1

    def list_template_codes(self, coordination_id: int) -> set[str]:
        with get_session() as session:
            stmt = select(CoordinationMeasure.template_code).where(
                CoordinationMeasure.coordination_id == coordination_id,
                CoordinationMeasure.template_code.is_not(None),
                CoordinationMeasure.template_code != "",
            )
            return {code for code in session.scalars(stmt) if code}
