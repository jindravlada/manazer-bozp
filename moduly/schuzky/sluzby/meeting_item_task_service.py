"""Úkoly navázané na konkrétní bod jednání."""

from __future__ import annotations

from core.shared.constants import ENTITY_MEETING
from moduly.schuzky.constants import AGENDA_ITEM_CHECK_PREFIX
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


def agenda_item_check_code(item_id: int) -> str:
    return f"{AGENDA_ITEM_CHECK_PREFIX}{int(item_id)}"[:100]


class MeetingItemTaskService:
    def list_for_item(self, meeting_id: int, item_id: int) -> list[Task]:
        code = agenda_item_check_code(item_id)
        tasks = task_service.repository.list_by_source(
            source_module=ENTITY_MEETING,
            source_record_id=int(meeting_id),
        )
        return [
            task
            for task in tasks
            if (task.source_check_code or "").strip() == code
        ]

    def create_for_item(
        self,
        *,
        meeting_id: int,
        item_id: int,
        title: str,
        description: str = "",
        priority: str = "Normální",
        due_date=None,
        responsible_person_id: int | None = None,
        workplace_id: int | None = None,
        completed: bool = False,
        completed_date=None,
        check_due_date=None,
        checked_date=None,
        checked_by_id: int | None = None,
        canceled: bool = False,
        note: str = "",
        requires_verification: bool | None = None,
    ) -> Task:
        return task_service.create_task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            responsible_person_id=responsible_person_id,
            workplace_id=workplace_id,
            completed=completed,
            completed_date=completed_date,
            check_due_date=check_due_date,
            checked_date=checked_date,
            checked_by_id=checked_by_id,
            canceled=canceled,
            note=note,
            requires_verification=requires_verification,
            source_module=ENTITY_MEETING,
            source_record_id=int(meeting_id),
            source_check_code=agenda_item_check_code(item_id),
        )

    def unlink_task(self, task_id: int) -> Task | None:
        task = task_service.get_task_by_id(task_id)
        if task is None:
            return None
        task.source_module = "manual"
        task.source_record_id = None
        task.source_check_code = ""
        return task_service.repository.update(task)

    def unlink_all_for_item(self, meeting_id: int, item_id: int) -> None:
        for task in self.list_for_item(meeting_id, item_id):
            self.unlink_task(task.id)


meeting_item_task_service = MeetingItemTaskService()
