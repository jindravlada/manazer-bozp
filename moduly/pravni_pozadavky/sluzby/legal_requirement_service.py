import calendar
from datetime import date

from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_NENI_RELEVANTNI,
    DEFAULT_PROCESSING_STATUS,
    PERIODICITY_MONTHS,
    VALID_COMPLIANCE_STATUSES,
    VALID_PERIODICITIES,
    VALID_PROCESSING_STATUSES,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.modely.legal_requirement_check import LegalRequirementCheck
from moduly.pravni_pozadavky.repository.legal_document_repository import LegalDocumentRepository
from moduly.pravni_pozadavky.repository.legal_requirement_check_repository import (
    LegalRequirementCheckRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_repository import (
    LegalRequirementRepository,
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
        self.check_repository = LegalRequirementCheckRepository()
        self.document_repository = LegalDocumentRepository()

    def get_all(self, *, active_only: bool | None = None) -> list[LegalRequirement]:
        return self.repository.get_all(active_only=active_only)

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
        return self.repository.list_source_section_ids(section_ids=section_ids)

    def create_requirement(
        self,
        *,
        regulation_name: str = "",
        regulation_number: str = "",
        provision: str = "",
        area: str = "",
        legal_document_id: int | None = None,
        legal_section_id: int | None = None,
        source_section_id: int | None = None,
        requirement_summary: str = "",
        organization_impact: str = "",
        responsible_person_id: int | None = None,
        verification_periodicity: str = "",
        last_verification_date: date | None = None,
        next_verification_date: date | None = None,
        compliance_status: str = "",
        processing_status: str = DEFAULT_PROCESSING_STATUS,
        note: str = "",
        active: bool = True,
    ) -> LegalRequirement:
        self._validate_legal_document_id(legal_document_id)
        self._validate_legal_section_id(legal_section_id)
        self._validate_source_section_id(source_section_id)

        requirement = LegalRequirement(
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
            verification_periodicity=self._normalize_periodicity(verification_periodicity),
            last_verification_date=last_verification_date,
            next_verification_date=next_verification_date,
            compliance_status=self._normalize_compliance_status(compliance_status),
            processing_status=self._normalize_processing_status(processing_status),
            note=note.strip(),
            active=active,
        )
        return self.repository.add(requirement)

    def update_requirement(
        self,
        requirement_id: int,
        *,
        regulation_name: str = "",
        regulation_number: str = "",
        provision: str = "",
        area: str = "",
        legal_document_id: int | None = None,
        legal_section_id: int | None = None,
        source_section_id: int | None = None,
        requirement_summary: str = "",
        organization_impact: str = "",
        responsible_person_id: int | None = None,
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

        self._validate_legal_document_id(legal_document_id)
        self._validate_legal_section_id(legal_section_id)
        self._validate_source_section_id(source_section_id)

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
        requirement.verification_periodicity = self._normalize_periodicity(verification_periodicity)
        requirement.last_verification_date = last_verification_date
        requirement.next_verification_date = next_verification_date
        requirement.compliance_status = self._normalize_compliance_status(compliance_status)
        requirement.processing_status = self._normalize_processing_status(processing_status)
        requirement.note = note.strip()
        requirement.active = active
        return self.repository.update(requirement)

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

    def _person_name(self, person_id: int | None) -> str:
        if person_id is None:
            return ""
        worker = settings_service.get_worker_by_id(person_id)
        if worker is None:
            return ""
        return worker.full_name

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

    def _normalize_processing_status(self, value: str) -> str:
        normalized = (value or "").strip()
        if normalized in VALID_PROCESSING_STATUSES:
            return normalized
        return DEFAULT_PROCESSING_STATUS


legal_requirement_service = LegalRequirementService()
