from moduly.pravni_pozadavky.constants import (
    CHANGE_SECTION_ADDED,
    CHANGE_SECTION_MODIFIED,
    CHANGE_SECTION_REMOVED,
    VALID_CHANGE_SECTION_TYPES,
)
from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
from moduly.pravni_pozadavky.repository.legal_change_section_repository import (
    LegalChangeSectionRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
    SectionStructureCompareResult,
)


class LegalChangeSectionService:
    def __init__(self):
        self.repository = LegalChangeSectionRepository()

    def list_sections_for_change(self, legal_change_id: int) -> list[LegalChangeSection]:
        self._validate_change_id(legal_change_id)
        return self.repository.list_by_change(legal_change_id)

    def add_sections_to_change(
        self,
        legal_change_id: int,
        compare_result: SectionStructureCompareResult,
    ) -> list[LegalChangeSection]:
        self._validate_change_id(legal_change_id)
        records: list[LegalChangeSection] = []
        for entry in compare_result.new:
            records.append(
                self._build_record(
                    legal_change_id=legal_change_id,
                    section_key=entry.identity_key,
                    section_label=entry.log_label,
                    change_type=CHANGE_SECTION_ADDED,
                ),
            )
        for entry in compare_result.removed:
            records.append(
                self._build_record(
                    legal_change_id=legal_change_id,
                    section_key=entry.identity_key,
                    section_label=entry.log_label,
                    change_type=CHANGE_SECTION_REMOVED,
                ),
            )
        for entry in compare_result.changed:
            records.append(
                self._build_record(
                    legal_change_id=legal_change_id,
                    section_key=entry.identity_key,
                    section_label=entry.log_label,
                    change_type=CHANGE_SECTION_MODIFIED,
                ),
            )
        return self.repository.create_many(records)

    def _build_record(
        self,
        *,
        legal_change_id: int,
        section_key: str,
        section_label: str,
        change_type: str,
        note: str | None = None,
    ) -> LegalChangeSection:
        normalized_type = change_type.strip()
        if normalized_type not in VALID_CHANGE_SECTION_TYPES:
            raise ValueError("Neplatný typ změny ustanovení.")
        normalized_key = section_key.strip()
        normalized_label = section_label.strip()
        if not normalized_key:
            raise ValueError("Identifikátor ustanovení je povinný.")
        if not normalized_label:
            raise ValueError("Popisek ustanovení je povinný.")
        return LegalChangeSection(
            legal_change_id=legal_change_id,
            section_key=normalized_key,
            section_label=normalized_label,
            change_type=normalized_type,
            note=(note or "").strip() or None,
        )

    def _validate_change_id(self, legal_change_id: int) -> None:
        if not isinstance(legal_change_id, int) or legal_change_id <= 0:
            raise ValueError("Neplatná zjištěná změna.")
        if legal_change_service.get_by_id(legal_change_id) is None:
            raise ValueError("Zjištěná změna nebyla nalezena.")


legal_change_section_service = LegalChangeSectionService()
