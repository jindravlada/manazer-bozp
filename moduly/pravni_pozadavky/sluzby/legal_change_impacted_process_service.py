import re
from dataclasses import dataclass

from moduly.pravni_pozadavky.constants import (
    legal_change_section_impact_label,
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
    change_type: str
    is_changed: bool = True

    @property
    def display_label(self) -> str:
        return legal_change_section_impact_label(self.label, self.change_type)


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
        change_types = self._resolve_section_change_types(change_sections, sections)
        if not change_types:
            return []

        requirements = self._find_requirements_for_sections(sorted(change_types))
        return self._build_process_list(
            requirements,
            change_types=change_types,
            sections_by_id=sections_by_id,
        )

    def _load_sections_for_change(self, change) -> tuple[list, dict]:
        version_ids: list[int] = []
        if change.legal_document_version_id is not None:
            version_ids.append(change.legal_document_version_id)
        if (
            change.new_legal_document_version_id is not None
            and change.new_legal_document_version_id not in version_ids
        ):
            version_ids.append(change.new_legal_document_version_id)
        if not version_ids:
            version = legal_document_version_service.get_current_version(change.legal_document_id)
            if version is not None:
                version_ids.append(version.id)

        sections: list = []
        for version_id in version_ids:
            sections.extend(
                legal_section_service.list_by_version(version_id, include_inactive=False),
            )
        if not sections:
            sections = legal_section_service.list_by_document(
                change.legal_document_id,
                include_inactive=False,
            )
        sections_by_id = {section.id: section for section in sections}
        return sections, sections_by_id

    def _resolve_section_ids(self, change, change_sections, sections: list) -> list[int]:
        return sorted(self._resolve_section_change_types(change_sections, sections))

    def _resolve_section_change_types(self, change_sections, sections: list) -> dict[int, str]:
        if not sections:
            return {}

        by_version: dict[int | None, list] = {}
        for section in sections:
            by_version.setdefault(section.legal_document_version_id, []).append(section)

        change_types: dict[int, str] = {}
        for group in by_version.values():
            for section_id, change_type in self._resolve_section_change_types_in_group(
                change_sections,
                group,
            ).items():
                change_types[section_id] = change_type
        return change_types

    def _resolve_section_ids_in_group(self, change_sections, sections: list) -> set[int]:
        return set(self._resolve_section_change_types_in_group(change_sections, sections))

    def _resolve_section_change_types_in_group(
        self,
        change_sections,
        sections: list,
    ) -> dict[int, str]:
        by_id = {section.id: section for section in sections}
        key_index = legal_section_structure_compare_service.build_section_key_index(sections)
        resolved: dict[int, str] = {}

        for change_section in change_sections:
            section_id = key_index.get(change_section.section_key)
            if section_id is not None:
                resolved[section_id] = change_section.change_type
                continue
            for section in sections:
                provision_label = legal_section_provision_label(section, sections_by_id=by_id)
                if self._labels_match(change_section.section_label, provision_label):
                    resolved[section.id] = change_section.change_type
                    continue
                log_label = legal_section_structure_compare_service.build_section_log_label(
                    section,
                    sections_by_id=by_id,
                )
                if self._labels_match(change_section.section_label, log_label):
                    resolved[section.id] = change_section.change_type

        return resolved

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
        change_types: dict[int, str],
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
                    change_types=change_types,
                    sections_by_id=sections_by_id,
                ),
            )
            if not legal_sources:
                continue
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
        change_types: dict[int, str],
        sections_by_id: dict,
    ) -> list[ImpactedProcessLegalSource]:
        sources: list[ImpactedProcessLegalSource] = []
        seen_ids: set[int] = set()
        for link in self.source_repository.list_by_requirement(requirement_id):
            if link.legal_section_id not in change_types:
                continue
            if link.legal_section_id in seen_ids:
                continue
            seen_ids.add(link.legal_section_id)
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
                    change_type=change_types[link.legal_section_id],
                    is_changed=True,
                ),
            )
        sources.sort(key=lambda item: (item.label.casefold(), item.section_id))
        return sources

    def _labels_match(self, left: str, right: str) -> bool:
        return self._normalize_provision_label(left) == self._normalize_provision_label(right)

    def _normalize_provision_label(self, label: str) -> str:
        normalized = (label or "").strip().casefold()
        normalized = normalized.replace("§", "§ ")
        normalized = _PROVISION_LABEL_RE.sub(" ", normalized)
        return normalized.strip()


legal_change_impacted_process_service = LegalChangeImpactedProcessService()
