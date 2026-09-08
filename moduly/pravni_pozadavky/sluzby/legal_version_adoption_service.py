from dataclasses import dataclass, field

from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.repository.legal_requirement_repository import (
    LegalRequirementRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
    LegalRequirementSourceRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
    legal_section_structure_compare_service,
)


@dataclass(frozen=True)
class UnresolvedSectionLink:
    requirement_id: int
    requirement_title: str
    section_id: int
    section_label: str
    section_key: str


@dataclass
class VersionAdoptionResult:
    adopted_version: LegalDocumentVersion
    previous_version: LegalDocumentVersion | None
    remapped_count: int
    unresolved_links: list[UnresolvedSectionLink] = field(default_factory=list)


class LegalVersionAdoptionService:
    def __init__(self):
        self.requirement_repository = LegalRequirementRepository()
        self.source_repository = LegalRequirementSourceRepository()

    def can_adopt(self, change) -> bool:
        detected = self._detected_version(change)
        return detected is not None and bool(detected.pending_adoption)

    def list_unresolved_section_links(self, change) -> list[UnresolvedSectionLink]:
        old_id, new_id = self._version_ids(change)
        if old_id is None or new_id is None:
            return []
        mapping, unresolved_ids = self._section_mapping(old_id, new_id)
        return self._collect_unresolved_links(unresolved_ids)

    def adopt_detected_version(self, change_id: int) -> VersionAdoptionResult:
        change = legal_change_service.get_by_id(change_id)
        if change is None:
            raise ValueError("Zjištěná změna nebyla nalezena.")
        if change.new_legal_document_version_id is None:
            raise ValueError("Změna nemá nové znění k převzetí.")

        detected = legal_document_version_service.get_by_id(change.new_legal_document_version_id)
        if detected is None:
            raise ValueError("Nové znění nebylo nalezeno.")
        if not detected.pending_adoption:
            raise ValueError("Nové znění už bylo převzato.")

        previous = None
        if change.legal_document_version_id is not None:
            previous = legal_document_version_service.get_by_id(change.legal_document_version_id)

        remapped_count = 0
        unresolved: list[UnresolvedSectionLink] = []
        if previous is not None:
            mapping, unresolved_ids = self._section_mapping(previous.id, detected.id)
            remapped_count = self._remap_links(mapping)
            if change.legal_section_id in mapping:
                legal_change_service.remap_legal_section_id(
                    change.id,
                    mapping[change.legal_section_id],
                )
            unresolved = self._collect_unresolved_links(unresolved_ids)

        adopted = legal_document_version_service.set_pending_adoption(detected.id, False)
        if adopted is None:
            raise ValueError("Nové znění se nepodařilo převzít.")

        return VersionAdoptionResult(
            adopted_version=adopted,
            previous_version=previous,
            remapped_count=remapped_count,
            unresolved_links=unresolved,
        )

    def _detected_version(self, change):
        if change is None or change.new_legal_document_version_id is None:
            return None
        return legal_document_version_service.get_by_id(change.new_legal_document_version_id)

    def _version_ids(self, change) -> tuple[int | None, int | None]:
        return change.legal_document_version_id, change.new_legal_document_version_id

    def _section_mapping(
        self,
        old_version_id: int,
        new_version_id: int,
    ) -> tuple[dict[int, int], set[int]]:
        old_sections = legal_section_service.list_by_version(old_version_id, include_inactive=True)
        new_sections = legal_section_service.list_by_version(new_version_id, include_inactive=True)
        old_by_id = {section.id: section for section in old_sections}
        old_unique = legal_section_structure_compare_service.build_unique_section_key_index(
            old_sections,
        )
        new_unique = legal_section_structure_compare_service.build_unique_section_key_index(
            new_sections,
        )

        mapping: dict[int, int] = {}
        unresolved_ids: set[int] = set()
        for section in old_sections:
            key = legal_section_structure_compare_service.section_identity_key(
                section,
                sections_by_id=old_by_id,
            )
            new_section_id = new_unique.get(key) if key in old_unique else None
            if new_section_id is None:
                unresolved_ids.add(section.id)
                continue
            mapping[section.id] = new_section_id
        return mapping, unresolved_ids

    def _remap_links(self, mapping: dict[int, int]) -> int:
        remapped = 0
        for old_section_id, new_section_id in mapping.items():
            remapped += self._remap_sources(old_section_id, new_section_id)
            remapped += self._remap_requirement_fields(old_section_id, new_section_id)
        return remapped

    def _remap_sources(self, old_section_id: int, new_section_id: int) -> int:
        remapped = 0
        existing_new = self.source_repository.list_by_section_ids([new_section_id])
        existing_requirement_ids = {source.requirement_id for source in existing_new}
        for source in self.source_repository.list_by_section_ids([old_section_id]):
            if source.requirement_id in existing_requirement_ids:
                self.source_repository.delete(source.id)
                remapped += 1
                continue
            source.legal_section_id = new_section_id
            self.source_repository.update(source)
            remapped += 1
        return remapped

    def _remap_requirement_fields(self, old_section_id: int, new_section_id: int) -> int:
        remapped = 0
        for requirement in self.requirement_repository.list_by_section_reference(old_section_id):
            changed = False
            if requirement.legal_section_id == old_section_id:
                requirement.legal_section_id = new_section_id
                changed = True
            if requirement.source_section_id == old_section_id:
                requirement.source_section_id = new_section_id
                changed = True
            if changed:
                self.requirement_repository.update(requirement)
                remapped += 1
        return remapped

    def _collect_unresolved_links(
        self,
        unresolved_ids: set[int],
    ) -> list[UnresolvedSectionLink]:
        if not unresolved_ids:
            return []

        sections = []
        for section_id in sorted(unresolved_ids):
            section = legal_section_service.get_by_id(section_id)
            if section is not None:
                sections.append(section)
        sections_by_id = {section.id: section for section in sections}
        linked_requirement_ids: dict[int, set[int]] = {section_id: set() for section_id in unresolved_ids}

        for source in self.source_repository.list_by_section_ids(sorted(unresolved_ids)):
            linked_requirement_ids.setdefault(source.legal_section_id, set()).add(source.requirement_id)
        for requirement in self.requirement_repository.list_by_source_section_ids(sorted(unresolved_ids)):
            if requirement.source_section_id is not None:
                linked_requirement_ids.setdefault(requirement.source_section_id, set()).add(requirement.id)
        for section_id in unresolved_ids:
            for requirement in self.requirement_repository.list_by_section_reference(section_id):
                linked_requirement_ids.setdefault(section_id, set()).add(requirement.id)

        links: list[UnresolvedSectionLink] = []
        seen: set[tuple[int, int]] = set()
        for section in sections:
            requirement_ids = linked_requirement_ids.get(section.id) or set()
            if not requirement_ids:
                continue
            key = legal_section_structure_compare_service.section_identity_key(
                section,
                sections_by_id=sections_by_id,
            )
            label = legal_section_structure_compare_service.build_section_log_label(
                section,
                sections_by_id=sections_by_id,
            )
            for requirement_id in sorted(requirement_ids):
                pair = (requirement_id, section.id)
                if pair in seen:
                    continue
                seen.add(pair)
                requirement = self.requirement_repository.get_by_id(requirement_id)
                title = ""
                if requirement is not None:
                    title = (
                        (requirement.process_code or "").strip()
                        or (requirement.title or "").strip()
                        or (requirement.regulation_name or "").strip()
                        or f"Požadavek #{requirement.id}"
                    )
                links.append(
                    UnresolvedSectionLink(
                        requirement_id=requirement_id,
                        requirement_title=title,
                        section_id=section.id,
                        section_label=label,
                        section_key=key,
                    ),
                )
        return links


legal_version_adoption_service = LegalVersionAdoptionService()
