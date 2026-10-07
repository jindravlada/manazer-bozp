from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
)
from moduly.nastaveni.modely.employer import Employer
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.workplace import Workplace
from moduly.nastaveni.repository.settings_repository import SettingsRepository
from moduly.nastaveni.sluzby.workplace_hierarchy_service import (
    WorkplaceHierarchyError,
    workplace_hierarchy_service,
    workplace_item_type_label,
)


class SettingsEmployerError(ValueError):
    pass


class SettingsService:
    def __init__(self):
        self.repository = SettingsRepository()

    # Zaměstnavatel
    def get_employer(self) -> Employer | None:
        return self.repository.get_employer()

    def save_employer(self, **data) -> Employer:
        employer = self.repository.get_employer()
        if "abbreviation" in data:
            data["abbreviation"] = self._validate_abbreviation(
                data.get("abbreviation"),
                exclude_employer_id=employer.id if employer is not None else None,
            )

        if employer is None:
            employer = Employer(**data)
        else:
            for key, value in data.items():
                if hasattr(employer, key):
                    setattr(employer, key, value)

        return self.repository.save_employer(employer)

    def _validate_abbreviation(
        self,
        abbreviation: str | None,
        *,
        exclude_employer_id: int | None = None,
    ) -> str:
        stored = " ".join((abbreviation or "").strip().split())
        if len(stored) > 32:
            raise SettingsEmployerError("Zkratka může mít nejvýše 32 znaků.")
        if not stored:
            return ""

        for item in self.repository.list_employers():
            if exclude_employer_id is not None and item.id == exclude_employer_id:
                continue
            other = " ".join((item.abbreviation or "").strip().split())
            if other and other.casefold() == stored.casefold():
                raise SettingsEmployerError(
                    f"Zkratka „{stored}“ je již použita."
                )
        return stored

    # THP pracovníci
    def get_workers(self, include_inactive: bool = False) -> list[ThpWorker]:
        return self.repository.get_workers(include_inactive=include_inactive)

    def get_workers_for_controls(self) -> list[ThpWorker]:
        return self.repository.get_workers_for_controls()

    def get_worker_by_id(self, worker_id: int | None, session=None) -> ThpWorker | None:
        if not worker_id:
            return None
        return self.repository.get_worker_by_id(worker_id, session=session)

    def save_worker(self, **data) -> ThpWorker:
        worker_id = data.pop("id", None)

        if worker_id:
            worker = self.repository.get_worker_by_id(worker_id)
            if worker is None:
                worker = ThpWorker(**data)
            else:
                for key, value in data.items():
                    if hasattr(worker, key):
                        setattr(worker, key, value)
        else:
            worker = ThpWorker(**data)

        return self.repository.save_worker(worker)

    def deactivate_worker(self, worker_id: int) -> bool:
        worker = self.repository.get_worker_by_id(worker_id)
        if worker is None:
            return False

        worker.active = False
        self.repository.save_worker(worker)
        return True

    def activate_worker(self, worker_id: int) -> bool:
        worker = self.repository.get_worker_by_id(worker_id)
        if worker is None:
            return False

        worker.active = True
        self.repository.save_worker(worker)
        return True

    # Provozy a pracoviště
    def get_workplaces(self, include_inactive: bool = False) -> list[Workplace]:
        workplaces = self.repository.get_workplaces(include_inactive=include_inactive)
        return workplace_hierarchy_service.sort_for_tree(workplaces)

    def get_workplace_by_id(self, workplace_id: int | None, session=None) -> Workplace | None:
        if not workplace_id:
            return None
        return self.repository.get_workplace_by_id(workplace_id, session=session)

    def get_workplace_parent_candidates(
        self,
        *,
        item_type: str,
        current_id: int | None = None,
        active_only: bool = True,
    ) -> list[Workplace]:
        workplaces = self.repository.get_workplaces(include_inactive=True)
        return workplace_hierarchy_service.parent_candidates(
            workplaces,
            item_type=item_type,
            current_id=current_id,
            active_only=active_only,
        )

    def get_active_workplace_children(self, workplace_id: int) -> list[Workplace]:
        workplaces = self.repository.get_workplaces(include_inactive=True)
        return workplace_hierarchy_service.active_children(workplaces, workplace_id)

    def save_workplace(self, **data) -> Workplace:
        workplace_id = data.pop("id", None)
        name = str(data.get("name", "")).strip()
        if not name:
            raise WorkplaceHierarchyError("Název je povinný.")

        item_type = str(data.get("item_type") or WORKPLACE_ITEM_TYPE_OPERATION).strip()
        parent_id = data.get("parent_id")
        if parent_id in ("", 0):
            parent_id = None

        all_workplaces = self.repository.get_workplaces(include_inactive=True)
        workplace_hierarchy_service.validate(
            all_workplaces,
            workplace_id=workplace_id,
            item_type=item_type,
            parent_id=parent_id,
        )

        if item_type == WORKPLACE_ITEM_TYPE_OPERATION:
            parent_id = None
            data["parent_id"] = None
        else:
            data["parent_id"] = parent_id

        data["name"] = name
        data["item_type"] = item_type

        if workplace_id:
            workplace = self.repository.get_workplace_by_id(workplace_id)
            if workplace is None:
                workplace = Workplace(**data)
            else:
                for key, value in data.items():
                    if hasattr(workplace, key):
                        setattr(workplace, key, value)
        else:
            workplace = Workplace(**data)

        return self.repository.save_workplace(workplace)

    def deactivate_workplace(self, workplace_id: int) -> bool:
        workplace = self.repository.get_workplace_by_id(workplace_id)
        if workplace is None:
            return False

        workplace.active = False
        self.repository.save_workplace(workplace)
        return True

    def activate_workplace(self, workplace_id: int) -> bool:
        workplace = self.repository.get_workplace_by_id(workplace_id)
        if workplace is None:
            return False

        workplace.active = True
        self.repository.save_workplace(workplace)
        return True

    @staticmethod
    def workplace_item_type_label(item_type: str) -> str:
        return workplace_item_type_label(item_type)


settings_service = SettingsService()
