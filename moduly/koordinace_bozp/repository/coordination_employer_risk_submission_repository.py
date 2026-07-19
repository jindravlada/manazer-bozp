from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
    CoordinationEmployerRiskSubmission,
)


class CoordinationEmployerRiskSubmissionRepository:
    def get_for_employer(
        self,
        coordination_employer_id: int,
    ) -> CoordinationEmployerRiskSubmission | None:
        with get_session() as session:
            stmt = select(CoordinationEmployerRiskSubmission).where(
                CoordinationEmployerRiskSubmission.coordination_employer_id
                == coordination_employer_id,
            )
            return session.scalars(stmt).first()

    def get_by_id(
        self,
        submission_id: int,
    ) -> CoordinationEmployerRiskSubmission | None:
        with get_session() as session:
            return session.get(CoordinationEmployerRiskSubmission, submission_id)

    def add(
        self,
        submission: CoordinationEmployerRiskSubmission,
    ) -> CoordinationEmployerRiskSubmission:
        with get_session() as session:
            session.add(submission)
            session.commit()
            session.refresh(submission)
            return submission

    def update(
        self,
        submission: CoordinationEmployerRiskSubmission,
    ) -> CoordinationEmployerRiskSubmission:
        with get_session() as session:
            submission = session.merge(submission)
            session.commit()
            session.refresh(submission)
            return submission
