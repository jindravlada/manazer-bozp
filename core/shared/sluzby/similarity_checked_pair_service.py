"""Služba evidence zkontrolovaných dvojic podobných záznamů (SIMILARITY-3)."""

from __future__ import annotations

from datetime import datetime

from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair
from core.shared.repository.similarity_checked_pair_repository import (
    SimilarityCheckedPairRepository,
)

# Obecné typy entit pro budoucí rozšíření (PBP, audity, rizika, …).
SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT = "proverky_kontrolni_otazka"
SIMILARITY_ENTITY_PBP = "pbp"
SIMILARITY_ENTITY_AUDIT_ASSERTION = "auditni_tvrzeni"
SIMILARITY_ENTITY_RISK = "riziko"
SIMILARITY_ENTITY_MEASURE = "opatreni"
SIMILARITY_ENTITY_LEGAL_REQUIREMENT = "pravni_pozadavek"


def normalize_similarity_pair_ids(
    left_entity_id: str,
    right_entity_id: str,
) -> tuple[str, str]:
    """Vrátí (left, right) s left = min(id), right = max(id)."""
    left = str(left_entity_id or "").strip()
    right = str(right_entity_id or "").strip()
    if not left or not right:
        raise ValueError("Obě ID dvojice musí být neprázdná.")
    if left == right:
        raise ValueError("Dvojice nesmí obsahovat stejné ID.")
    if left <= right:
        return left, right
    return right, left


class SimilarityCheckedPairService:
    def __init__(self) -> None:
        self.repository = SimilarityCheckedPairRepository()

    def normalize_ids(
        self,
        left_entity_id: str,
        right_entity_id: str,
    ) -> tuple[str, str]:
        return normalize_similarity_pair_ids(left_entity_id, right_entity_id)

    def is_checked(
        self,
        entity_type: str,
        left_entity_id: str,
        right_entity_id: str,
    ) -> bool:
        left, right = normalize_similarity_pair_ids(left_entity_id, right_entity_id)
        return (
            self.repository.get(str(entity_type).strip(), left, right) is not None
        )

    def list_checked_keys(self, entity_type: str) -> set[tuple[str, str]]:
        """Množina normalizovaných (left_id, right_id) pro daný typ."""
        return {
            (record.left_entity_id, record.right_entity_id)
            for record in self.repository.list_for_type(str(entity_type).strip())
        }

    def mark_checked(
        self,
        entity_type: str,
        left_entity_id: str,
        right_entity_id: str,
        *,
        checked_by: str = "",
    ) -> SimilarityCheckedPair:
        left, right = normalize_similarity_pair_ids(left_entity_id, right_entity_id)
        entity_type = str(entity_type).strip()
        existing = self.repository.get(entity_type, left, right)
        if existing is not None:
            return existing

        record = SimilarityCheckedPair(
            entity_type=entity_type,
            left_entity_id=left,
            right_entity_id=right,
            checked_at=datetime.now(),
            checked_by=str(checked_by or "").strip(),
        )
        return self.repository.add(record)

    def unmark_checked(
        self,
        entity_type: str,
        left_entity_id: str,
        right_entity_id: str,
    ) -> bool:
        left, right = normalize_similarity_pair_ids(left_entity_id, right_entity_id)
        return self.repository.delete(str(entity_type).strip(), left, right)


similarity_checked_pair_service = SimilarityCheckedPairService()
