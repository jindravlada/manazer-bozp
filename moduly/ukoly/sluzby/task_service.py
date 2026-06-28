from datetime import date, timedelta

from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.modely.task import Task
from moduly.ukoly.repository.task_repository import TaskRepository


class TaskService:
    def __init__(self):
        self.repository = TaskRepository()

    def get_all_tasks(self):
        return self.repository.get_all()

    def get_task_by_id(self, task_id: int):
        return self.repository.get_by_id(task_id)

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "Normální",
        due_date: date | None = None,
        responsible_person_id: int | None = None,
        workplace_id: int | None = None,
        completed: bool = False,
        completed_date: date | None = None,
        requires_verification: bool = False,
        check_due_date: date | None = None,
        checked_date: date | None = None,
        checked_by_id: int | None = None,
        canceled: bool = False,
        note: str = "",
        source_module: str = "manual",
        source_record_id: int | None = None,
    ) -> Task:
        if source_module != "manual":
            requires_verification = True

        if completed and completed_date is None:
            completed_date = date.today()

        if completed and requires_verification and check_due_date is None:
            check_due_date = completed_date + timedelta(days=15)

        task = Task(
            title=title,
            description=description,
            status="Aktivní",
            priority=priority,
            due_date=due_date,
            responsible_person_id=responsible_person_id,
            responsible_person=self._person_name(responsible_person_id),
            workplace_id=workplace_id,
            workplace_name=self._workplace_name(workplace_id),
            completed=completed,
            completed_date=completed_date,
            requires_verification=requires_verification,
            check_due_date=check_due_date if requires_verification else None,
            checked_date=checked_date if requires_verification else None,
            checked_by_id=checked_by_id if requires_verification else None,
            checked_by_name=self._person_name(checked_by_id) if requires_verification else "",
            canceled=canceled,
            note=note,
            source_module=source_module,
            source_record_id=source_record_id,
        )
        self._sync_legacy_status(task)
        return self.repository.add(task)

    def update_task(
        self,
        task_id: int,
        title: str,
        description: str = "",
        priority: str = "Normální",
        due_date: date | None = None,
        responsible_person_id: int | None = None,
        workplace_id: int | None = None,
        completed: bool = False,
        completed_date: date | None = None,
        requires_verification: bool = False,
        check_due_date: date | None = None,
        checked_date: date | None = None,
        checked_by_id: int | None = None,
        canceled: bool = False,
        note: str = "",
    ) -> Task | None:
        task = self.repository.get_by_id(task_id)
        if task is None:
            return None

        if completed and completed_date is None:
            completed_date = date.today()

        if completed and requires_verification and check_due_date is None:
            check_due_date = completed_date + timedelta(days=15)

        task.title = title
        task.description = description
        task.priority = priority
        task.due_date = due_date
        task.responsible_person_id = responsible_person_id
        task.responsible_person = self._person_name(responsible_person_id)
        task.workplace_id = workplace_id
        task.workplace_name = self._workplace_name(workplace_id)
        task.completed = completed
        task.completed_date = completed_date if completed else None
        task.requires_verification = requires_verification
        task.check_due_date = check_due_date if requires_verification else None
        task.checked_date = checked_date if requires_verification else None
        task.checked_by_id = checked_by_id if requires_verification else None
        task.checked_by_name = self._person_name(checked_by_id) if requires_verification else ""
        task.canceled = canceled
        task.note = note
        self._sync_legacy_status(task)

        return self.repository.update(task)

    def mark_completed(self, task_id: int) -> bool:
        task = self.repository.get_by_id(task_id)
        if task is None:
            return False

        task.completed = True
        if task.completed_date is None:
            task.completed_date = date.today()

        if task.requires_verification and task.check_due_date is None:
            task.check_due_date = task.completed_date + timedelta(days=15)

        self._sync_legacy_status(task)
        self.repository.update(task)
        return True

    def reopen_task(self, task_id: int) -> bool:
        task = self.repository.get_by_id(task_id)
        if task is None:
            return False

        task.completed = False
        task.completed_date = None
        task.check_due_date = None
        task.checked_date = None
        task.checked_by_id = None
        task.checked_by_name = ""
        task.canceled = False
        self._sync_legacy_status(task)

        self.repository.update(task)
        return True

    def cancel_task(self, task_id: int) -> bool:
        task = self.repository.get_by_id(task_id)
        if task is None:
            return False

        task.canceled = True
        self._sync_legacy_status(task)
        self.repository.update(task)
        return True

    def _sync_legacy_status(self, task: Task) -> None:
        task.status = task.computed_status

    def _person_name(self, person_id: int | None) -> str:
        if not person_id:
            return ""

        person = settings_service.get_worker_by_id(person_id)
        return person.display_name if person else ""

    def _workplace_name(self, workplace_id: int | None) -> str:
        if not workplace_id:
            return ""

        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace else ""


task_service = TaskService()
