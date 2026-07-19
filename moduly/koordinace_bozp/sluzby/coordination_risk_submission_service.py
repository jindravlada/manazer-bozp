"""Služba předání rizik dodavatelů (COORD-006)."""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    RISK_HANDOVER_STATUS_MAIN,
    RISK_HANDOVER_STATUS_NOT_SUBMITTED,
    RISK_HANDOVER_STATUS_WITH_ATTACHMENT,
    RISK_HANDOVER_STATUS_WITHOUT_ATTACHMENT,
    RISK_SUBMISSION_METHOD_NOT_SUBMITTED,
    RISK_SUBMISSION_METHODS,
)
from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
    CoordinationEmployerRiskSubmission,
)
from moduly.koordinace_bozp.repository.coordination_attachment_repository import (
    CoordinationAttachmentRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_risk_submission_repository import (
    CoordinationEmployerRiskSubmissionRepository,
)


class CoordinationRiskSubmissionError(ValueError):
    pass


class CoordinationRiskSubmissionService:
    def __init__(self) -> None:
        self.repository = CoordinationEmployerRiskSubmissionRepository()
        self.employer_repository = CoordinationEmployerRepository()
        self.attachment_repository = CoordinationAttachmentRepository()

    def get_for_employer(
        self,
        coordination_employer_id: int,
    ) -> CoordinationEmployerRiskSubmission | None:
        return self.repository.get_for_employer(coordination_employer_id)

    def save_submission(
        self,
        coordination_employer_id: int,
        *,
        submission_method: str,
        submission_date: date | None = None,
        document_reference: str = "",
        note: str = "",
    ) -> CoordinationEmployerRiskSubmission:
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            raise CoordinationRiskSubmissionError("Zaměstnavatel nebyl nalezen.")
        if employer.is_main:
            raise CoordinationRiskSubmissionError(
                "Hlavní zaměstnavatel vlastní předání dodavatelských rizik nevyplňuje."
            )
        if submission_method not in RISK_SUBMISSION_METHODS:
            raise CoordinationRiskSubmissionError("Neplatný způsob předání rizik.")

        existing = self.repository.get_for_employer(coordination_employer_id)
        if existing is None:
            submission = CoordinationEmployerRiskSubmission(
                coordination_employer_id=coordination_employer_id,
                submission_method=submission_method,
                submission_date=submission_date,
                document_reference=(document_reference or "").strip(),
                note=(note or "").strip(),
                active=True,
            )
            return self.repository.add(submission)

        existing.submission_method = submission_method
        existing.submission_date = submission_date
        existing.document_reference = (document_reference or "").strip()
        existing.note = (note or "").strip()
        existing.active = True
        existing.updated_at = datetime.now()
        return self.repository.update(existing)

    def handover_status(self, coordination_employer_id: int) -> str:
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            return RISK_HANDOVER_STATUS_NOT_SUBMITTED
        if employer.is_main:
            return RISK_HANDOVER_STATUS_MAIN

        submission = self.repository.get_for_employer(coordination_employer_id)
        attachments = self.attachment_repository.list_for_employer(
            coordination_employer_id,
            include_inactive=False,
        )
        method = (
            submission.submission_method
            if submission is not None
            else RISK_SUBMISSION_METHOD_NOT_SUBMITTED
        )
        if method == RISK_SUBMISSION_METHOD_NOT_SUBMITTED or submission is None:
            if attachments:
                return RISK_HANDOVER_STATUS_WITH_ATTACHMENT
            return RISK_HANDOVER_STATUS_NOT_SUBMITTED
        if attachments:
            return RISK_HANDOVER_STATUS_WITH_ATTACHMENT
        return RISK_HANDOVER_STATUS_WITHOUT_ATTACHMENT


coordination_risk_submission_service = CoordinationRiskSubmissionService()
