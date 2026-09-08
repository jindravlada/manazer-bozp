from moduly.pravni_pozadavky.constants import (
    CHANGE_SECTION_ADDED,
    CHANGE_SECTION_MODIFIED,
    CHANGE_SECTION_REMOVED,
    VALID_CHANGE_SECTION_TYPES,
)
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
from moduly.pravni_pozadavky.repository.legal_change_section_repository import (
    LegalChangeSectionRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
    SectionStructureCompareResult,
    SectionStructureEntry,
    legal_section_structure_compare_service,
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
        records = self._records_from_result(legal_change_id, compare_result)
        return self.repository.create_many(records)

    def sync_version_content_changes(
        self,
        change: LegalChange,
    ) -> tuple[list[LegalChangeSection], SectionStructureCompareResult]:
        self._validate_change_id(change.id)
        old_version_id = change.legal_document_version_id
        new_version_id = change.new_legal_document_version_id
        if old_version_id is None or new_version_id is None:
            return self.list_sections_for_change(change.id), SectionStructureCompareResult()

        compare_result = legal_section_structure_compare_service.compare_version_sections(
            old_sections=legal_section_service.list_by_version(
                old_version_id,
                include_inactive=False,
            ),
            new_sections=legal_section_service.list_by_version(
                new_version_id,
                include_inactive=False,
            ),
        )
        desired = self._records_from_result(change.id, compare_result)
        existing = self.list_sections_for_change(change.id)
        if self._same_payload(existing, desired):
            return existing, compare_result
        saved = self.repository.replace_for_change(change.id, desired)
        return saved, compare_result

    def _records_from_result(
        self,
        legal_change_id: int,
        compare_result: SectionStructureCompareResult,
    ) -> list[LegalChangeSection]:
        records: list[LegalChangeSection] = []
        for entry in compare_result.new:
            records.append(
                self._build_record(
                    legal_change_id=legal_change_id,
                    entry=entry,
                    change_type=CHANGE_SECTION_ADDED,
                ),
            )
        for entry in compare_result.removed:
            records.append(
                self._build_record(
                    legal_change_id=legal_change_id,
                    entry=entry,
                    change_type=CHANGE_SECTION_REMOVED,
                ),
            )
        for entry in compare_result.changed:
            records.append(
                self._build_record(
                    legal_change_id=legal_change_id,
                    entry=entry,
                    change_type=CHANGE_SECTION_MODIFIED,
                ),
            )
        return records

    def _build_record(
        self,
        *,
        legal_change_id: int,
        entry: SectionStructureEntry,
        change_type: str,
        note: str | None = None,
    ) -> LegalChangeSection:
        normalized_type = change_type.strip()
        if normalized_type not in VALID_CHANGE_SECTION_TYPES:
            raise ValueError("Neplatný typ změny ustanovení.")
        normalized_key = entry.identity_key.strip()
        normalized_label = entry.log_label.strip()
        if not normalized_key:
            raise ValueError("Identifikátor ustanovení je povinný.")
        if not normalized_label:
            raise ValueError("Popisek ustanovení je povinný.")
        old_text = entry.old_text
        new_text = entry.new_text
        if old_text is None and new_text is None and (entry.text or "").strip():
            if normalized_type == CHANGE_SECTION_ADDED:
                new_text = entry.text
            elif normalized_type == CHANGE_SECTION_REMOVED:
                old_text = entry.text
        return LegalChangeSection(
            legal_change_id=legal_change_id,
            section_key=normalized_key,
            section_label=normalized_label,
            change_type=normalized_type,
            old_text=(old_text or "").strip() or None,
            new_text=(new_text or "").strip() or None,
            note=(note or "").strip() or None,
        )

    def _same_payload(
        self,
        existing: list[LegalChangeSection],
        desired: list[LegalChangeSection],
    ) -> bool:
        def _row(item: LegalChangeSection) -> tuple:
            return (
                item.change_type,
                item.section_key,
                item.section_label,
                item.old_text or None,
                item.new_text or None,
            )

        return sorted(map(_row, existing)) == sorted(map(_row, desired))

    def _validate_change_id(self, legal_change_id: int) -> None:
        if not isinstance(legal_change_id, int) or legal_change_id <= 0:
            raise ValueError("Neplatná zjištěná změna.")
        if legal_change_service.get_by_id(legal_change_id) is None:
            raise ValueError("Zjištěná změna nebyla nalezena.")


legal_change_section_service = LegalChangeSectionService()
