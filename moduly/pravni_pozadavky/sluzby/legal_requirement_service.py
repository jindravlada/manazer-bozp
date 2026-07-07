import calendar
from datetime import date

from sqlalchemy import delete, update

from core.database.session import get_session
from core.shared.constants import ENTITY_LEGAL_REQUIREMENT
from core.shared.sluzby.entity_link_service import entity_link_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_NENI_RELEVANTNI,
    DEFAULT_PROCESSING_STATUS,
    PERIODICITY_MONTHS,
    PROCESSING_APPROVED,
    REQUIREMENT_STATUS_APPROVED,
    REQUIREMENT_STATUS_EXISTS,
    VALID_COMPLIANCE_STATUSES,
    VALID_PERIODICITIES,
    VALID_PROCESSING_STATUSES,
    format_process_code,
    parse_process_code_number,
)
from moduly.ukoly.modely.task import Task
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.modely.legal_requirement_check import LegalRequirementCheck
from moduly.pravni_pozadavky.modely.legal_requirement_sanction import LegalRequirementSanction
from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
from moduly.pravni_pozadavky.repository.legal_document_repository import LegalDocumentRepository
from moduly.pravni_pozadavky.repository.legal_requirement_check_repository import (
    LegalRequirementCheckRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_repository import (
    LegalRequirementRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
    LegalRequirementSourceRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


def _add_months(value: date, months: int) -> date:
    year = value.year
    month = value.month + months
    while month > 12:
        year += 1
        month -= 12
    while month < 1:
        year -= 1
        month += 12
    last_day = calendar.monthrange(year, month)[1]
    day = min(value.day, last_day)
    return date(year, month, day)


def calculate_next_verification_date(
    check_date: date,
    periodicity: str,
    *,
    explicit_next_date: date | None = None,
) -> date | None:
    if explicit_next_date is not None:
        return explicit_next_date

    months = PERIODICITY_MONTHS.get(periodicity)
    if months is None:
        return None
    return _add_months(check_date, months)


class LegalRequirementService:
    def __init__(self):
        self.repository = LegalRequirementRepository()
        self.source_repository = LegalRequirementSourceRepository()
        self.check_repository = LegalRequirementCheckRepository()
        self.document_repository = LegalDocumentRepository()

    def get_all(self, *, active_only: bool | None = None) -> list[LegalRequirement]:
        return self.repository.get_all(active_only=active_only)

    def list_active_processes(self) -> list[LegalRequirement]:
        from core.utils.czech_sort import czech_sorted

        processes = self.repository.get_all(active_only=True)
        return czech_sorted(
            processes,
            key=lambda item: item.title or item.regulation_name or "",
        )

    def attach_source_section(
        self,
        requirement_id: int,
        section_id: int,
    ) -> LegalRequirement:
        requirement = self.repository.get_by_id(requirement_id)
        if requirement is None:
            raise ValueError("Proces nebyl nalezen.")
        if not requirement.active:
            raise ValueError("Proces není aktivní.")

        existing_requirement = self.get_by_source_section_id(section_id)
        if existing_requirement is not None and existing_requirement.id != requirement_id:
            raise ValueError("Ustanovení je již přiřazeno jinému procesu.")

        self._validate_source_section_id(section_id)

        section_ids = self.list_source_section_ids_for_requirement(requirement_id)
        if section_id in section_ids:
            return requirement

        section_ids.append(section_id)
        self.source_repository.replace_for_requirement(requirement_id, section_ids)

        requirement = self.repository.get_by_id(requirement_id)
        if requirement is None:
            raise ValueError("Proces nebyl nalezen.")
        if requirement.source_section_id is None:
            requirement.source_section_id = section_ids[0]
            requirement = self.repository.update(requirement)
        return requirement

    def get_by_id(self, requirement_id: int) -> LegalRequirement | None:
        return self.repository.get_by_id(requirement_id)

    def get_checks(self, requirement_id: int) -> list[LegalRequirementCheck]:
        return self.check_repository.get_by_requirement_id(requirement_id)

    def get_distinct_areas(self) -> list[str]:
        areas = {
            requirement.area.strip()
            for requirement in self.repository.get_all()
            if requirement.area.strip()
        }
        return sorted(areas)

    def get_source_section_ids(self, section_ids: list[int] | None = None) -> set[int]:
        linked = self.source_repository.list_linked_section_ids(section_ids=section_ids)
        legacy = self.repository.list_source_section_ids(section_ids=section_ids)
        return linked | legacy

    def list_source_section_ids_for_requirement(self, requirement_id: int) -> list[int]:
        section_ids = self.source_repository.list_section_ids_by_requirement(requirement_id)
        if section_ids:
            return section_ids
        requirement = self.repository.get_by_id(requirement_id)
        if requirement is not None and requirement.source_section_id is not None:
            return [requirement.source_section_id]
        return []

    def get_by_source_section_id(self, section_id: int) -> LegalRequirement | None:
        requirement_id = self.source_repository.get_first_requirement_id_by_section(section_id)
        if requirement_id is not None:
            return self.repository.get_by_id(requirement_id)
        requirement = self.repository.get_by_source_section_id(section_id)
        if requirement is not None and not requirement.active:
            return None
        return requirement

    def section_has_requirement(self, section_id: int) -> bool:
        return self.get_by_source_section_id(section_id) is not None

    def get_source_section_requirement_statuses(
        self,
        section_ids: list[int],
    ) -> dict[int, str]:
        statuses: dict[int, str] = {}
        if not section_ids:
            return statuses

        for link in self.source_repository.list_by_section_ids(section_ids):
            requirement = self.repository.get_by_id(link.requirement_id)
            if requirement is None or not requirement.active:
                continue
            section_id = link.legal_section_id
            if requirement.processing_status == PROCESSING_APPROVED:
                statuses[section_id] = REQUIREMENT_STATUS_APPROVED
            elif section_id not in statuses:
                statuses[section_id] = REQUIREMENT_STATUS_EXISTS

        for requirement in self.repository.list_by_source_section_ids(section_ids):
            if requirement.source_section_id is None:
                continue
            section_id = requirement.source_section_id
            if section_id in statuses:
                continue
            if not requirement.active:
                continue
            if requirement.processing_status == PROCESSING_APPROVED:
                statuses[section_id] = REQUIREMENT_STATUS_APPROVED
            else:
                statuses[section_id] = REQUIREMENT_STATUS_EXISTS
        return statuses

    def create_requirement(
        self,
        *,
        title: str = "",
        regulation_name: str = "",
        regulation_number: str = "",
        provision: str = "",
        area: str = "",
        legal_document_id: int | None = None,
        legal_section_id: int | None = None,
        source_section_id: int | None = None,
        source_section_ids: list[int] | None = None,
        requirement_summary: str = "",
        organization_impact: str = "",
        responsible_person_id: int | None = None,
        responsible_role_id: int | None = None,
        verification_periodicity: str = "",
        last_verification_date: date | None = None,
        next_verification_date: date | None = None,
        compliance_status: str = "",
        processing_status: str = DEFAULT_PROCESSING_STATUS,
        note: str = "",
        active: bool = True,
    ) -> LegalRequirement:
        resolved_source_ids = self._resolve_source_section_ids(
            source_section_ids=source_section_ids,
            source_section_id=source_section_id,
        )
        if resolved_source_ids and source_section_id is None:
            source_section_id = resolved_source_ids[0]
        if resolved_source_ids and legal_section_id is None:
            legal_section_id = resolved_source_ids[0]

        self._validate_legal_document_id(legal_document_id)
        self._validate_legal_section_id(legal_section_id)
        self._validate_source_section_ids(resolved_source_ids)
        self._validate_responsible_role_id(responsible_role_id)

        requirement = LegalRequirement(
            title=title.strip(),
            process_code=self._allocate_process_code(),
            regulation_name=regulation_name.strip(),
            regulation_number=regulation_number.strip(),
            provision=provision.strip(),
            area=area.strip(),
            legal_document_id=legal_document_id,
            legal_section_id=legal_section_id,
            source_section_id=source_section_id,
            requirement_summary=requirement_summary.strip(),
            organization_impact=organization_impact.strip(),
            responsible_person_id=responsible_person_id,
            responsible_person_name=self._person_name(responsible_person_id),
            responsible_role_id=responsible_role_id,
            responsible_role_name=self._role_name(responsible_role_id),
            verification_periodicity=self._normalize_periodicity(verification_periodicity),
            last_verification_date=last_verification_date,
            next_verification_date=next_verification_date,
            compliance_status=self._normalize_compliance_status(compliance_status),
            processing_status=self._normalize_processing_status(processing_status),
            note=note.strip(),
            active=active,
        )
        requirement = self.repository.add(requirement)
        if resolved_source_ids:
            self.source_repository.replace_for_requirement(requirement.id, resolved_source_ids)
            requirement.source_section_id = resolved_source_ids[0]
            requirement = self.repository.update(requirement)
        return requirement

    def update_requirement(
        self,
        requirement_id: int,
        *,
        title: str | None = None,
        regulation_name: str = "",
        regulation_number: str = "",
        provision: str = "",
        area: str = "",
        legal_document_id: int | None = None,
        legal_section_id: int | None = None,
        source_section_id: int | None = None,
        source_section_ids: list[int] | None = None,
        requirement_summary: str = "",
        organization_impact: str = "",
        responsible_person_id: int | None = None,
        responsible_role_id: int | None = None,
        verification_periodicity: str = "",
        last_verification_date: date | None = None,
        next_verification_date: date | None = None,
        compliance_status: str = "",
        processing_status: str = DEFAULT_PROCESSING_STATUS,
        note: str = "",
        active: bool = True,
    ) -> LegalRequirement | None:
        requirement = self.repository.get_by_id(requirement_id)
        if requirement is None:
            return None

        resolved_source_ids = (
            self._resolve_source_section_ids(
                source_section_ids=source_section_ids,
                source_section_id=source_section_id,
            )
            if source_section_ids is not None
            else None
        )
        if resolved_source_ids is not None:
            source_section_id = resolved_source_ids[0] if resolved_source_ids else None

        self._validate_legal_document_id(legal_document_id)
        self._validate_legal_section_id(legal_section_id)
        if resolved_source_ids is not None:
            self._validate_source_section_ids(resolved_source_ids)
        else:
            self._validate_source_section_id(source_section_id)
        self._validate_responsible_role_id(responsible_role_id)

        if title is not None:
            requirement.title = title.strip()
        requirement.regulation_name = regulation_name.strip()
        requirement.regulation_number = regulation_number.strip()
        requirement.provision = provision.strip()
        requirement.area = area.strip()
        requirement.legal_document_id = legal_document_id
        requirement.legal_section_id = legal_section_id
        requirement.source_section_id = source_section_id
        requirement.requirement_summary = requirement_summary.strip()
        requirement.organization_impact = organization_impact.strip()
        requirement.responsible_person_id = responsible_person_id
        requirement.responsible_person_name = self._person_name(responsible_person_id)
        requirement.responsible_role_id = responsible_role_id
        requirement.responsible_role_name = self._role_name(responsible_role_id)
        requirement.verification_periodicity = self._normalize_periodicity(verification_periodicity)
        requirement.last_verification_date = last_verification_date
        requirement.next_verification_date = next_verification_date
        requirement.compliance_status = self._normalize_compliance_status(compliance_status)
        requirement.processing_status = self._normalize_processing_status(processing_status)
        requirement.note = note.strip()
        requirement.active = active
        requirement = self.repository.update(requirement)
        if resolved_source_ids is not None:
            self.source_repository.replace_for_requirement(requirement_id, resolved_source_ids)
        return requirement

    def archive_requirement(self, requirement_id: int) -> LegalRequirement | None:
        requirement = self.repository.get_by_id(requirement_id)
        if requirement is None:
            return None
        requirement.active = False
        return self.repository.update(requirement)

    def restore_requirement(self, requirement_id: int) -> LegalRequirement | None:
        requirement = self.repository.get_by_id(requirement_id)
        if requirement is None:
            return None
        requirement.active = True
        return self.repository.update(requirement)

    def merge_process_requirements(
        self,
        source_id: int,
        target_id: int,
    ) -> LegalRequirement:
        if source_id == target_id:
            raise ValueError("Zdrojový a cílový proces musí být různé.")

        source = self.repository.get_by_id(source_id)
        target = self.repository.get_by_id(target_id)
        if source is None or target is None:
            raise ValueError("Proces nebyl nalezen.")
        if not source.active or not target.active:
            raise ValueError("Sloučit lze pouze aktivní procesy.")

        target_section_ids = self.list_source_section_ids_for_requirement(target_id)
        source_section_ids = self.list_source_section_ids_for_requirement(source_id)
        merged_section_ids = list(target_section_ids)
        for section_id in source_section_ids:
            if section_id not in merged_section_ids:
                merged_section_ids.append(section_id)

        self.source_repository.replace_for_requirement(target_id, merged_section_ids)
        target = self.repository.get_by_id(target_id)
        if target is not None and target.source_section_id is None and merged_section_ids:
            target.source_section_id = merged_section_ids[0]
            target = self.repository.update(target)

        with get_session() as session:
            session.execute(
                update(LegalRequirementCheck)
                .where(LegalRequirementCheck.legal_requirement_id == source_id)
                .values(legal_requirement_id=target_id),
            )
            session.execute(
                update(LegalRequirementSanction)
                .where(LegalRequirementSanction.requirement_id == source_id)
                .values(requirement_id=target_id),
            )
            session.execute(
                update(Task)
                .where(
                    Task.source_module == ENTITY_LEGAL_REQUIREMENT,
                    Task.source_record_id == source_id,
                )
                .values(source_record_id=target_id),
            )
            session.commit()

        entity_link_service.reassign_entity_id(
            ENTITY_LEGAL_REQUIREMENT,
            source_id,
            target_id,
        )
        self.source_repository.delete_by_requirement(source_id)

        source = self.repository.get_by_id(source_id)
        if source is None:
            raise ValueError("Zdrojový proces se nepodařilo archivovat.")
        source.merged_into_requirement_id = target_id
        source.active = False
        self.repository.update(source)

        merged = self.repository.get_by_id(target_id)
        if merged is None:
            raise ValueError("Cílový proces nebyl nalezen.")
        return merged

    def record_verification(
        self,
        requirement_id: int,
        *,
        check_date: date,
        result: str,
        comment: str = "",
        next_check_date: date | None = None,
    ) -> LegalRequirement | None:
        requirement = self.repository.get_by_id(requirement_id)
        if requirement is None:
            return None

        normalized_result = self._normalize_compliance_status(result)
        computed_next = calculate_next_verification_date(
            check_date,
            requirement.verification_periodicity,
            explicit_next_date=next_check_date,
        )

        check = LegalRequirementCheck(
            legal_requirement_id=requirement_id,
            check_date=check_date,
            result=normalized_result,
            comment=comment.strip(),
            next_check_date=computed_next,
        )
        self.check_repository.add(check)

        requirement.last_verification_date = check_date
        requirement.compliance_status = normalized_result
        requirement.next_verification_date = computed_next
        return self.repository.update(requirement)

    def delete_all_process_requirements(self) -> dict[str, int]:
        with get_session() as session:
            checks_deleted = session.execute(delete(LegalRequirementCheck)).rowcount or 0
            sanctions_deleted = session.execute(delete(LegalRequirementSanction)).rowcount or 0
            sources_deleted = session.execute(delete(LegalRequirementSource)).rowcount or 0
            requirements_deleted = session.execute(delete(LegalRequirement)).rowcount or 0
            session.commit()

        return {
            "requirements": requirements_deleted,
            "sources": sources_deleted,
            "checks": checks_deleted,
            "sanctions": sanctions_deleted,
        }

    def _allocate_process_code(self) -> str:
        max_number = 0
        for requirement in self.repository.get_all():
            number = parse_process_code_number(requirement.process_code)
            if number is not None:
                max_number = max(max_number, number)
        return format_process_code(max_number + 1)

    def _person_name(self, person_id: int | None) -> str:
        if person_id is None:
            return ""
        worker = settings_service.get_worker_by_id(person_id)
        if worker is None:
            return ""
        return worker.full_name

    def _role_name(self, role_id: int | None) -> str:
        return responsibility_role_service.display_name(role_id)

    def _validate_responsible_role_id(self, role_id: int | None) -> None:
        if role_id is None:
            return
        if not isinstance(role_id, int) or role_id <= 0:
            raise ValueError("Neplatná odpovědná role.")
        if responsibility_role_service.get_by_id(role_id) is None:
            raise ValueError("Odpovědná role nebyla nalezena.")

    def _normalize_periodicity(self, value: str) -> str:
        normalized = (value or "").strip()
        if normalized in VALID_PERIODICITIES:
            return normalized
        return ""

    def _normalize_compliance_status(self, value: str) -> str:
        normalized = (value or "").strip()
        if normalized in VALID_COMPLIANCE_STATUSES:
            return normalized
        return COMPLIANCE_NENI_RELEVANTNI

    def _validate_legal_document_id(self, legal_document_id: int | None) -> None:
        if legal_document_id is None:
            return
        if not isinstance(legal_document_id, int) or legal_document_id <= 0:
            raise ValueError("Neplatný právní předpis.")
        if self.document_repository.get_by_id(legal_document_id) is None:
            raise ValueError("Právní předpis nebyl nalezen.")

    def _validate_legal_section_id(self, legal_section_id: int | None) -> None:
        if legal_section_id is None:
            return
        if not isinstance(legal_section_id, int) or legal_section_id <= 0:
            raise ValueError("Neplatné ustanovení předpisu.")
        section = legal_section_service.get_by_id(legal_section_id)
        if section is None:
            raise ValueError("Ustanovení předpisu nebylo nalezeno.")
        if not section.active:
            raise ValueError("Ustanovení předpisu není aktivní.")

    def _validate_source_section_id(self, source_section_id: int | None) -> None:
        if source_section_id is None:
            return
        if not isinstance(source_section_id, int) or source_section_id <= 0:
            raise ValueError("Neplatné zdrojové ustanovení.")
        section = legal_section_service.get_by_id(source_section_id)
        if section is None:
            raise ValueError("Zdrojové ustanovení nebylo nalezeno.")

    def _validate_source_section_ids(self, section_ids: list[int]) -> None:
        for section_id in section_ids:
            self._validate_source_section_id(section_id)

    def _resolve_source_section_ids(
        self,
        *,
        source_section_ids: list[int] | None,
        source_section_id: int | None,
    ) -> list[int]:
        resolved: list[int] = []
        seen: set[int] = set()
        candidates = source_section_ids if source_section_ids is not None else []
        if not candidates and source_section_id is not None:
            candidates = [source_section_id]
        for section_id in candidates:
            if section_id is None or section_id in seen:
                continue
            seen.add(section_id)
            resolved.append(section_id)
        return resolved

    def _normalize_processing_status(self, value: str) -> str:
        normalized = (value or "").strip()
        if normalized in VALID_PROCESSING_STATUSES:
            return normalized
        return DEFAULT_PROCESSING_STATUS


legal_requirement_service = LegalRequirementService()
