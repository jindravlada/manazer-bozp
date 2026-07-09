import re
from dataclasses import dataclass

from moduly.pravni_pozadavky.constants import (
    legal_requirement_process_label,
    legal_section_provision_label,
    process_code_sort_key,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.repository.legal_requirement_repository import (
    LegalRequirementRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
    LegalRequirementSourceRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
    legal_change_section_service,
)
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
    legal_section_structure_compare_service,
)

_PROVISION_LABEL_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ImpactedControlProcess:
    process_code: str
    process_name: str


class LegalChangeImpactedProcessService:
    def __init__(self):
        self.requirement_repository = LegalRequirementRepository()
        self.source_repository = LegalRequirementSourceRepository()

    def list_processes_for_change(self, legal_change_id: int) -> list[ImpactedControlProcess]:
        change = legal_change_service.get_by_id(legal_change_id)
        if change is None:
            return []

        change_sections = legal_change_section_service.list_sections_for_change(legal_change_id)
        if not change_sections:
            return []

        section_ids = self._resolve_section_ids(change, change_sections)
        if not section_ids:
            return []

        requirements = self._find_requirements_for_sections(section_ids)
        return self._build_process_list(requirements)

    def _resolve_section_ids(self, change, change_sections) -> list[int]:
        version_id = change.legal_document_version_id
        if version_id is None:
            version = legal_document_version_service.get_current_version(change.legal_document_id)
            version_id = version.id if version is not None else None
        if version_id is None:
            return []

        sections = legal_section_service.list_by_version(version_id, include_inactive=False)
        if not sections:
            sections = legal_section_service.list_by_document(
                change.legal_document_id,
                include_inactive=False,
            )
        if not sections:
            return []

        by_id = {section.id: section for section in sections}
        key_index = legal_section_structure_compare_service.build_section_key_index(sections)
        resolved: set[int] = set()

        for change_section in change_sections:
            section_id = key_index.get(change_section.section_key)
            if section_id is not None:
                resolved.add(section_id)
                continue
            for section in sections:
                provision_label = legal_section_provision_label(section, sections_by_id=by_id)
                if self._labels_match(change_section.section_label, provision_label):
                    resolved.add(section.id)
                    continue
                log_label = legal_section_structure_compare_service.build_section_log_label(
                    section,
                    sections_by_id=by_id,
                )
                if self._labels_match(change_section.section_label, log_label):
                    resolved.add(section.id)

        return sorted(resolved)

    def _find_requirements_for_sections(self, section_ids: list[int]) -> list[LegalRequirement]:
        requirements: list[LegalRequirement] = []
        seen_ids: set[int] = set()

        for link in self.source_repository.list_by_section_ids(section_ids):
            requirement = self.requirement_repository.get_by_id(link.requirement_id)
            if requirement is None or not requirement.active:
                continue
            if requirement.id in seen_ids:
                continue
            seen_ids.add(requirement.id)
            requirements.append(requirement)

        for requirement in self.requirement_repository.list_by_source_section_ids(section_ids):
            if not requirement.active or requirement.id in seen_ids:
                continue
            seen_ids.add(requirement.id)
            requirements.append(requirement)

        return requirements

    def _build_process_list(
        self,
        requirements: list[LegalRequirement],
    ) -> list[ImpactedControlProcess]:
        processes: list[ImpactedControlProcess] = []
        seen_ids: set[int] = set()

        for requirement in sorted(requirements, key=process_code_sort_key):
            if requirement.id in seen_ids:
                continue
            seen_ids.add(requirement.id)
            processes.append(
                ImpactedControlProcess(
                    process_code=(requirement.process_code or "").strip(),
                    process_name=legal_requirement_process_label(requirement),
                ),
            )
        return processes

    def _labels_match(self, left: str, right: str) -> bool:
        return self._normalize_provision_label(left) == self._normalize_provision_label(right)

    def _normalize_provision_label(self, label: str) -> str:
        normalized = (label or "").strip().casefold()
        normalized = normalized.replace("§", "§ ")
        normalized = _PROVISION_LABEL_RE.sub(" ", normalized)
        return normalized.strip()


legal_change_impacted_process_service = LegalChangeImpactedProcessService()
