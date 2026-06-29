from moduly.nastaveni.modely.employer import Employer
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.workplace import Workplace
from moduly.nastaveni.repository.settings_repository import SettingsRepository


class SettingsService:
    def __init__(self):
        self.repository = SettingsRepository()

    # Zaměstnavatel
    def get_employer(self) -> Employer | None:
        return self.repository.get_employer()

    def save_employer(self, **data) -> Employer:
        employer = self.repository.get_employer()

        if employer is None:
            employer = Employer(**data)
        else:
            for key, value in data.items():
                if hasattr(employer, key):
                    setattr(employer, key, value)

        return self.repository.save_employer(employer)

    # THP pracovníci
    def get_workers(self, include_inactive: bool = False) -> list[ThpWorker]:
        return self.repository.get_workers(include_inactive=include_inactive)

    def get_workers_for_controls(self) -> list[ThpWorker]:
        return self.repository.get_workers_for_controls()

    def get_worker_by_id(self, worker_id: int | None) -> ThpWorker | None:
        if not worker_id:
            return None
        return self.repository.get_worker_by_id(worker_id)

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

    # Pracoviště
    def get_workplaces(self, include_inactive: bool = False) -> list[Workplace]:
        return self.repository.get_workplaces(include_inactive=include_inactive)

    def get_workplace_by_id(self, workplace_id: int | None) -> Workplace | None:
        if not workplace_id:
            return None
        return self.repository.get_workplace_by_id(workplace_id)

    def save_workplace(self, **data) -> Workplace:
        workplace_id = data.pop("id", None)

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


settings_service = SettingsService()
