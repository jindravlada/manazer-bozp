"""Repository pro schválení formulací PBP."""

from __future__ import annotations

from core.database.session import get_session
from moduly.rizeni_rizik.modely.pbp_validation_approval import PbpValidationApproval


class PbpValidationApprovalRepository:
    def get_for_measure_rule(
        self,
        measure_id: int,
        validation_rule_code: str,
    ) -> PbpValidationApproval | None:
        with get_session() as session:
            row = (
                session.query(PbpValidationApproval)
                .filter(
                    PbpValidationApproval.measure_id == int(measure_id),
                    PbpValidationApproval.validation_rule_code == validation_rule_code,
                )
                .one_or_none()
            )
            if row is None:
                return None
            session.expunge(row)
            return row

    def upsert(self, approval: PbpValidationApproval) -> PbpValidationApproval:
        with get_session() as session:
            existing = (
                session.query(PbpValidationApproval)
                .filter(
                    PbpValidationApproval.measure_id == int(approval.measure_id),
                    PbpValidationApproval.validation_rule_code
                    == approval.validation_rule_code,
                )
                .one_or_none()
            )
            if existing is None:
                session.add(approval)
                session.commit()
                session.refresh(approval)
                session.expunge(approval)
                return approval
            existing.approved_text_hash = approval.approved_text_hash
            session.commit()
            session.refresh(existing)
            session.expunge(existing)
            return existing

    def delete_for_measure_rule(
        self,
        measure_id: int,
        validation_rule_code: str,
    ) -> bool:
        with get_session() as session:
            existing = (
                session.query(PbpValidationApproval)
                .filter(
                    PbpValidationApproval.measure_id == int(measure_id),
                    PbpValidationApproval.validation_rule_code == validation_rule_code,
                )
                .one_or_none()
            )
            if existing is None:
                return False
            session.delete(existing)
            session.commit()
            return True
