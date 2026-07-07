from datetime import date, timedelta

from core.shared.constants import ENTITY_LEGAL_REQUIREMENT
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_CASTECNE_SPLNENO,
    COMPLIANCE_NESPLNENO,
    COMPLIANCE_STATUS_LABELS,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.ukoly.sluzby.task_service import task_service


class LegalRequirementTaskService:
    def can_create_task(self, requirement: LegalRequirement | None) -> bool:
        if requirement is None or not requirement.active:
            return False
        return requirement.compliance_status in (
            COMPLIANCE_NESPLNENO,
            COMPLIANCE_CASTECNE_SPLNENO,
        )

    def find_open_task(self, requirement_id: int):
        return task_service.repository.find_open_by_source(
            source_module=ENTITY_LEGAL_REQUIREMENT,
            source_record_id=requirement_id,
        )

    def create_task_from_requirement(
        self,
        requirement_id: int,
        *,
        due_date: date | None = None,
    ):
        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            raise ValueError("Právní požadavek nebyl nalezen.")
        if not self.can_create_task(requirement):
            raise ValueError("Úkol lze založit pouze u nesplněného nebo částečně splněného požadavku.")

        existing_task = self.find_open_task(requirement_id)
        if existing_task is not None:
            return existing_task

        if due_date is None:
            due_date = requirement.next_verification_date
        if due_date is None:
            due_date = date.today() + timedelta(days=30)

        title = self._task_title(requirement)
        description = self._task_description(requirement)

        return task_service.create_task(
            title=title,
            description=description,
            due_date=due_date,
            responsible_person_id=requirement.responsible_person_id,
            completed=False,
            requires_verification=True,
            source_module=ENTITY_LEGAL_REQUIREMENT,
            source_record_id=requirement.id,
        )

    def _task_title(self, requirement: LegalRequirement) -> str:
        summary = requirement.requirement_summary.strip()
        if summary:
            return summary[:200]

        regulation = requirement.regulation_name.strip()
        provision = requirement.provision.strip()
        if regulation and provision:
            return f"{regulation} – {provision}"[:200]
        if regulation:
            return regulation[:200]
        return f"Právní požadavek #{requirement.id}"

    def _task_description(self, requirement: LegalRequirement) -> str:
        parts = []
        if requirement.regulation_name.strip():
            parts.append(f"Předpis: {requirement.regulation_name.strip()}")
        if requirement.regulation_number.strip():
            parts.append(f"Číslo předpisu: {requirement.regulation_number.strip()}")
        if requirement.provision.strip():
            parts.append(f"Ustanovení: {requirement.provision.strip()}")
        if requirement.organization_impact.strip():
            parts.append(f"Dopad na organizaci:\n{requirement.organization_impact.strip()}")
        if requirement.compliance_status:
            label = COMPLIANCE_STATUS_LABELS.get(
                requirement.compliance_status,
                requirement.compliance_status,
            )
            parts.append(f"Stav plnění: {label}")
        return "\n\n".join(parts)


legal_requirement_task_service = LegalRequirementTaskService()
