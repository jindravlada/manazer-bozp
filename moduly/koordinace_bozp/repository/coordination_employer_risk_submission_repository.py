from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
    CoordinationEmployerRiskSubmission,
    CoordinationRiskSubmissionHistory,
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

    def add_history(
        self,
        entry: CoordinationRiskSubmissionHistory,
    ) -> CoordinationRiskSubmissionHistory:
        with get_session() as session:
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def list_history(
        self,
        submission_id: int,
    ) -> list[CoordinationRiskSubmissionHistory]:
        with get_session() as session:
            stmt = (
                select(CoordinationRiskSubmissionHistory)
                .where(CoordinationRiskSubmissionHistory.submission_id == submission_id)
                .order_by(
                    CoordinationRiskSubmissionHistory.created_at.asc(),
                    CoordinationRiskSubmissionHistory.id.asc(),
                )
            )
            return list(session.scalars(stmt).all())
