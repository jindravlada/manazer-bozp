from __future__ import annotations

from collections import defaultdict
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
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_section_tree import LegalSectionTree


@dataclass(frozen=True)
class DocumentSectionProcessUsage:
    requirement_id: int
    process_code: str
    process_name: str

    @property
    def display_label(self) -> str:
        code = (self.process_code or "").strip()
        name = (self.process_name or "").strip()
        if code and name:
            return f"{code} – {name}"
        if code:
            return code
        if name:
            return name
        return f"Proces #{self.requirement_id}"


@dataclass(frozen=True)
class DocumentSectionProcessUsageEntry:
    section_id: int
    provision_label: str
    processes: tuple[DocumentSectionProcessUsage, ...]
    is_assigned: bool


class LegalDocumentProcessUsageService:
    def __init__(self) -> None:
        self.requirement_repository = LegalRequirementRepository()
        self.source_repository = LegalRequirementSourceRepository()

    def list_process_usage_for_document(
        self,
        document_id: int,
    ) -> list[DocumentSectionProcessUsageEntry]:
        version = legal_document_version_service.get_current_version(document_id)
        if version is None:
            return []

        sections = legal_section_service.list_by_version(version.id, include_inactive=False)
        if not sections:
            return []

        sections_by_id = legal_section_service.build_sections_map(sections)
        processable_sections = [
            section
            for section in sections
            if section.active
            and LegalSectionTree.allows_requirement_creation(section.section_type)
        ]
        if not processable_sections:
            return []

        section_ids = [section.id for section in processable_sections]
        section_to_requirement_ids = self._map_sections_to_requirement_ids(section_ids)
        requirement_ids = {
            requirement_id
            for requirement_ids in section_to_requirement_ids.values()
            for requirement_id in requirement_ids
        }
        requirements_by_id = self._load_active_requirements(requirement_ids)

        rows: list[DocumentSectionProcessUsageEntry] = []
        for section in sorted(processable_sections, key=lambda item: (item.sort_order, item.id)):
            processes = self._build_processes_for_section(
                section_to_requirement_ids.get(section.id, set()),
                requirements_by_id=requirements_by_id,
            )
            rows.append(
                DocumentSectionProcessUsageEntry(
                    section_id=section.id,
                    provision_label=legal_section_provision_label(
                        section,
                        sections_by_id=sections_by_id,
                    ),
                    processes=processes,
                    is_assigned=bool(processes),
                ),
            )
        return rows

    def _map_sections_to_requirement_ids(
        self,
        section_ids: list[int],
    ) -> dict[int, set[int]]:
        section_to_requirement_ids: dict[int, set[int]] = defaultdict(set)

        for link in self.source_repository.list_by_section_ids(section_ids):
            section_to_requirement_ids[link.legal_section_id].add(link.requirement_id)

        for requirement in self.requirement_repository.list_by_source_section_ids(section_ids):
            if requirement.source_section_id is not None:
                section_to_requirement_ids[requirement.source_section_id].add(requirement.id)

        return section_to_requirement_ids

    def _load_active_requirements(
        self,
        requirement_ids: set[int],
    ) -> dict[int, LegalRequirement]:
        if not requirement_ids:
            return {}

        requirements = self.requirement_repository.list_by_ids(sorted(requirement_ids))
        return {
            requirement.id: requirement
            for requirement in requirements
            if requirement.active
        }

    def _build_processes_for_section(
        self,
        requirement_ids: set[int],
        *,
        requirements_by_id: dict[int, LegalRequirement],
    ) -> tuple[DocumentSectionProcessUsage, ...]:
        processes: list[DocumentSectionProcessUsage] = []
        seen_requirement_ids: set[int] = set()

        for requirement_id in sorted(
            requirement_ids,
            key=lambda item: process_code_sort_key(requirements_by_id[item])
            if item in requirements_by_id
            else (1, str(item)),
        ):
            if requirement_id in seen_requirement_ids:
                continue
            requirement = requirements_by_id.get(requirement_id)
            if requirement is None:
                continue
            seen_requirement_ids.add(requirement_id)
            processes.append(
                DocumentSectionProcessUsage(
                    requirement_id=requirement.id,
                    process_code=(requirement.process_code or "").strip(),
                    process_name=legal_requirement_process_label(requirement),
                ),
            )

        processes.sort(
            key=lambda item: process_code_sort_key(
                requirements_by_id.get(item.requirement_id),
            )
            if item.requirement_id in requirements_by_id
            else (1, item.process_code.lower()),
        )
        return tuple(processes)


legal_document_process_usage_service = LegalDocumentProcessUsageService()
