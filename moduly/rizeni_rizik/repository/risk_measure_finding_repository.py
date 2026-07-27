from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.risk_measure_finding import RiskMeasureFinding


class RiskMeasureFindingRepository:
    def list_for_review(self, review_id: int) -> list[RiskMeasureFinding]:
        with get_session() as session:
            stmt = (
                select(RiskMeasureFinding)
                .where(RiskMeasureFinding.review_id == review_id)
                .order_by(RiskMeasureFinding.note_number, RiskMeasureFinding.id)
            )
            return list(session.scalars(stmt))

    def get_by_id(self, finding_id: int) -> RiskMeasureFinding | None:
        with get_session() as session:
            return session.get(RiskMeasureFinding, finding_id)

    def get_by_review_and_note_number(
        self,
        review_id: int,
        note_number: str,
    ) -> RiskMeasureFinding | None:
        normalized = (note_number or "").strip()
        if not normalized:
            return None
        with get_session() as session:
            stmt = select(RiskMeasureFinding).where(
                RiskMeasureFinding.review_id == review_id,
                RiskMeasureFinding.note_number == normalized,
            )
            return session.scalars(stmt).first()

    def add(self, finding: RiskMeasureFinding) -> RiskMeasureFinding:
        with get_session() as session:
            session.add(finding)
            session.commit()
            session.refresh(finding)
            return finding

    def update(self, finding: RiskMeasureFinding) -> RiskMeasureFinding:
        with get_session() as session:
            finding = session.merge(finding)
            session.commit()
            session.refresh(finding)
            return finding
