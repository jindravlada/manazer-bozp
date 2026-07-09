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
class ImpactedProcessLegalSource:
    section_id: int
    label: str
    is_changed: bool


@dataclass(frozen=True)
class ImpactedControlProcess:
    requirement_id: int
    process_code: str
    process_name: str
    legal_sources: tuple[ImpactedProcessLegalSource, ...]

    @property
    def display_title(self) -> str:
        code = (self.process_code or "").strip()
        name = (self.process_name or "").strip()
        if code and name:
            return f"{code} {name}"
        if code:
            return code
        if name:
            return name
        return f"Proces #{self.requirement_id}"


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

        sections, sections_by_id = self._load_sections_for_change(change)
        changed_section_ids = set(self._resolve_section_ids(change, change_sections, sections))
        if not changed_section_ids:
            return []

        requirements = self._find_requirements_for_sections(sorted(changed_section_ids))
        return self._build_process_list(
            requirements,
            changed_section_ids=changed_section_ids,
            sections_by_id=sections_by_id,
        )

    def _load_sections_for_change(self, change) -> tuple[list, dict]:
        version_id = change.legal_document_version_id
        if version_id is None:
            version = legal_document_version_service.get_current_version(change.legal_document_id)
            version_id = version.id if version is not None else None

        sections: list = []
        if version_id is not None:
            sections = legal_section_service.list_by_version(version_id, include_inactive=False)
        if not sections:
            sections = legal_section_service.list_by_document(
                change.legal_document_id,
                include_inactive=False,
            )
        sections_by_id = {section.id: section for section in sections}
        return sections, sections_by_id

    def _resolve_section_ids(self, change, change_sections, sections: list) -> list[int]:
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
        *,
        changed_section_ids: set[int],
        sections_by_id: dict,
    ) -> list[ImpactedControlProcess]:
        processes: list[ImpactedControlProcess] = []
        seen_ids: set[int] = set()

        for requirement in sorted(requirements, key=process_code_sort_key):
            if requirement.id in seen_ids:
                continue
            seen_ids.add(requirement.id)
            legal_sources = tuple(
                self._build_legal_sources(
                    requirement.id,
                    changed_section_ids=changed_section_ids,
                    sections_by_id=sections_by_id,
                ),
            )
            processes.append(
                ImpactedControlProcess(
                    requirement_id=requirement.id,
                    process_code=(requirement.process_code or "").strip(),
                    process_name=legal_requirement_process_label(requirement),
                    legal_sources=legal_sources,
                ),
            )
        return processes

    def _build_legal_sources(
        self,
        requirement_id: int,
        *,
        changed_section_ids: set[int],
        sections_by_id: dict,
    ) -> list[ImpactedProcessLegalSource]:
        sources: list[ImpactedProcessLegalSource] = []
        for link in self.source_repository.list_by_requirement(requirement_id):
            section = sections_by_id.get(link.legal_section_id)
            if section is None:
                section = legal_section_service.get_by_id(link.legal_section_id)
            if section is None or not section.active:
                continue
            local_sections_by_id = sections_by_id
            if section.id not in local_sections_by_id:
                local_sections_by_id = {**sections_by_id, section.id: section}
            label = legal_section_structure_compare_service.build_section_log_label(
                section,
                sections_by_id=local_sections_by_id,
            )
            sources.append(
                ImpactedProcessLegalSource(
                    section_id=section.id,
                    label=label,
                    is_changed=section.id in changed_section_ids,
                ),
            )
        return sources

    def _labels_match(self, left: str, right: str) -> bool:
        return self._normalize_provision_label(left) == self._normalize_provision_label(right)

    def _normalize_provision_label(self, label: str) -> str:
        normalized = (label or "").strip().casefold()
        normalized = normalized.replace("§", "§ ")
        normalized = _PROVISION_LABEL_RE.sub(" ", normalized)
        return normalized.strip()


legal_change_impacted_process_service = LegalChangeImpactedProcessService()
