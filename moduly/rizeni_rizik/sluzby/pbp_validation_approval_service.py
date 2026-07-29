"""Služba uživatelských schválení kontroly PBP (UX-PBP-VALIDATION-1a)."""

from __future__ import annotations

import hashlib

from moduly.rizeni_rizik.modely.pbp_validation_approval import (
    PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE,
    PbpValidationApproval,
)
from moduly.rizeni_rizik.repository.pbp_validation_approval_repository import (
    PbpValidationApprovalRepository,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    PravidloBezpecnePrace,
    normalize_rule_text,
)


def approved_text_hash(text: str) -> str:
    normalized = normalize_rule_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class PbpValidationApprovalService:
    def __init__(self) -> None:
        self.repository = PbpValidationApprovalRepository()

    def is_rule_approved(
        self,
        rule: PravidloBezpecnePrace,
        *,
        validation_rule_code: str = PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE,
    ) -> bool:
        text_hash = approved_text_hash(rule.text)
        for measure_id in self._measure_ids(rule):
            approval = self.repository.get_for_measure_rule(
                measure_id,
                validation_rule_code,
            )
            if approval is not None and approval.approved_text_hash == text_hash:
                return True
        return False

    def approve_rule(
        self,
        rule: PravidloBezpecnePrace,
        *,
        validation_rule_code: str = PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE,
    ) -> None:
        text_hash = approved_text_hash(rule.text)
        for measure_id in self._measure_ids(rule):
            self.repository.upsert(
                PbpValidationApproval(
                    measure_id=int(measure_id),
                    validation_rule_code=validation_rule_code,
                    approved_text_hash=text_hash,
                )
            )

    def revoke_rule(
        self,
        rule: PravidloBezpecnePrace,
        *,
        validation_rule_code: str = PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE,
    ) -> None:
        for measure_id in self._measure_ids(rule):
            self.repository.delete_for_measure_rule(measure_id, validation_rule_code)

    @staticmethod
    def _measure_ids(rule: PravidloBezpecnePrace) -> list[int]:
        ids = [int(source.measure_id) for source in rule.sources]
        if not ids:
            ids = [int(rule.measure_id)]
        # unikátní se zachováním pořadí
        seen: set[int] = set()
        unique: list[int] = []
        for measure_id in ids:
            if measure_id in seen:
                continue
            seen.add(measure_id)
            unique.append(measure_id)
        return unique


pbp_validation_approval_service = PbpValidationApprovalService()
