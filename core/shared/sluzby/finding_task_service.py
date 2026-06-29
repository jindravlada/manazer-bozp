from datetime import date

from core.shared.constants import ENTITY_FINDING, FINDING_STATUS_VYPORADANO
from core.shared.finding_display import finding_type_label
from core.shared.modely.finding import Finding
from core.shared.sluzby.finding_service import finding_service
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


class FindingTaskService:
    def get_linked_task(self, finding: Finding | None) -> Task | None:
        if finding is None or not finding.task_id:
            return None

        task = task_service.get_task_by_id(finding.task_id)
        if task is None:
            return None
        return task

    def get_finding_for_task(self, task: Task | None) -> Finding | None:
        if task is None:
            return None

        if task.source_module == ENTITY_FINDING and task.source_record_id:
            finding = finding_service.get_by_id(task.source_record_id)
            if finding is not None:
                return finding

        return finding_service.get_by_task_id(task.id)

    def get_task_action(self, finding_id: int | None) -> str:
        if finding_id is None:
            return "hidden"

        finding = finding_service.get_by_id(finding_id)
        if finding is None or finding.status == FINDING_STATUS_VYPORADANO:
            return "hidden"

        task = self.get_linked_task(finding)
        if task is None:
            return "create"
        return "open"

    def is_task_verified(self, task: Task) -> bool:
        if task.canceled or not task.completed:
            return False
        if task.requires_verification:
            return task.checked_date is not None
        return True

    def create_task_from_finding(self, finding_id: int) -> Task:
        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            raise ValueError("Zjištění nebylo nalezeno.")

        existing_task = self.get_linked_task(finding)
        if existing_task is not None:
            return existing_task

        title = self._task_title(finding)
        description = self._task_description(finding)

        task = task_service.create_task(
            title=title,
            description=description,
            due_date=finding.due_date,
            responsible_person_id=finding.responsible_person_id,
            completed=False,
            completed_date=None,
            checked_date=None,
            requires_verification=True,
            source_module=ENTITY_FINDING,
            source_record_id=finding.id,
        )

        if finding.responsible_person_name and not task.responsible_person:
            task.responsible_person = finding.responsible_person_name
            task_service.repository.update(task)

        finding_service.update(finding_id, task_id=task.id)
        return task

    def resolve_finding_for_verified_task(self, task: Task | None) -> Finding | None:
        if task is None or not self.is_task_verified(task):
            return None

        finding = self.get_finding_for_task(task)
        if finding is None or finding.status == FINDING_STATUS_VYPORADANO:
            return None

        return finding_service.update(
            finding.id,
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date.today(),
        )

    def _task_title(self, finding: Finding) -> str:
        if finding.recommended_action.strip():
            title = finding.recommended_action.strip()
        elif finding.description.strip():
            title = finding.description.strip().splitlines()[0].strip()
        elif finding.reference_label.strip():
            title = f"Opatření – {finding.reference_label.strip()}"
        else:
            title = f"Opatření – {finding_type_label(finding.finding_type)}"

        return title[:200]

    def _task_description(self, finding: Finding) -> str:
        parts = []
        if finding.description.strip():
            parts.append(finding.description.strip())
        if finding.recommended_action.strip():
            parts.append(f"Doporučené opatření:\n{finding.recommended_action.strip()}")
        if finding.reference_label.strip():
            parts.append(f"Reference: {finding.reference_label.strip()}")
        return "\n\n".join(parts)


finding_task_service = FindingTaskService()
