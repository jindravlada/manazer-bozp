from datetime import date, timedelta

from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.constants import DEFAULT_TASK_TYPE, TASK_TYPE_INVESTIGATION_ACTION
from moduly.ukoly.modely.task import Task
from moduly.ukoly.repository.task_repository import TaskRepository


class TaskService:
    def __init__(self):
        self.repository = TaskRepository()

    def get_all_tasks(self):
        return self.repository.get_all()

    def get_task_by_id(self, task_id: int):
        return self.repository.get_by_id(task_id)

    def find_open_investigation_action(
        self,
        investigation_id: int,
        title: str,
    ):
        from core.shared.constants import ENTITY_MU_INVESTIGATION

        return self.repository.find_open_by_source(
            source_module=ENTITY_MU_INVESTIGATION,
            source_record_id=investigation_id,
            task_type=TASK_TYPE_INVESTIGATION_ACTION,
            title=title.strip(),
        )

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "Normální",
        due_date: date | None = None,
        remind_from: date | None = None,
        responsible_person_id: int | None = None,
        workplace_id: int | None = None,
        completed: bool = False,
        completed_date: date | None = None,
        check_due_date: date | None = None,
        checked_date: date | None = None,
        checked_by_id: int | None = None,
        canceled: bool = False,
        note: str = "",
        source_module: str = "manual",
        source_record_id: int | None = None,
        task_type: str = DEFAULT_TASK_TYPE,
        source_check_code: str = "",
        requires_verification: bool | None = None,
    ) -> Task:
        if requires_verification is None:
            if task_type == TASK_TYPE_INVESTIGATION_ACTION:
                requires_verification = False
            else:
                requires_verification = source_module != "manual"

        if completed and completed_date is None:
            completed_date = date.today()

        if completed and requires_verification and check_due_date is None:
            check_due_date = completed_date + timedelta(days=15)

        remind_from = self._normalized_remind_from(remind_from, due_date)

        task = Task(
            title=title,
            description=description,
            status="Aktivní",
            priority=priority,
            due_date=due_date,
            remind_from=remind_from,
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
            task_type=task_type,
            source_check_code=source_check_code,
        )
        self._sync_legacy_status(task)
        saved = self.repository.add(task)
        return saved

    def update_task(
        self,
        task_id: int,
        title: str,
        description: str = "",
        priority: str = "Normální",
        due_date: date | None = None,
        remind_from: date | None = None,
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

        remind_from = self._normalized_remind_from(remind_from, due_date)

        task.title = title
        task.description = description
        task.priority = priority
        task.due_date = due_date
        task.remind_from = remind_from
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

        saved = self.repository.update(task)
        self._resolve_linked_finding(saved)
        return saved

    @staticmethod
    def validate_remind_from(
        remind_from: date | None,
        due_date: date | None,
    ) -> str | None:
        """Vrátí chybovou hlášku, pokud je remind_from neplatné."""
        if remind_from is None or due_date is None:
            return None
        if remind_from > due_date:
            return "Připomenout od nemůže být později než termín splnění."
        return None

    @classmethod
    def _normalized_remind_from(
        cls,
        remind_from: date | None,
        due_date: date | None,
    ) -> date | None:
        error = cls.validate_remind_from(remind_from, due_date)
        if error:
            raise ValueError(error)
        return remind_from

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
        saved = self.repository.update(task)
        self._resolve_linked_finding(saved)
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

        saved = self.repository.update(task)
        self._reopen_linked_finding(saved)
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

    def _resolve_linked_finding(self, task: Task | None) -> None:
        if task is None:
            return

        from core.shared.sluzby.finding_task_service import finding_task_service

        finding_task_service.resolve_finding_for_verified_task(task)

    def _reopen_linked_finding(self, task: Task | None) -> None:
        if task is None:
            return

        from core.shared.sluzby.finding_task_service import finding_task_service

        finding_task_service.reopen_finding_for_task(task)

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
