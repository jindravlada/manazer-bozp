from sqlalchemy.exc import IntegrityError

from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
)
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
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


class SettingsWorkerError(ValueError):
    pass


_WORKER_TEXT_FIELDS = (
    "title_before",
    "first_name",
    "last_name",
    "title_after",
    "position",
    "phone",
    "email",
)


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

    # Evidence zaměstnanců (tabulka thp_workers).
    def get_workers(
        self,
        include_inactive: bool = False,
        *,
        leading_only: bool = False,
    ) -> list[ThpWorker]:
        return self.repository.get_workers(
            include_inactive=include_inactive,
            leading_only=leading_only,
        )

    def get_workers_for_controls(self) -> list[ThpWorker]:
        return self.repository.get_workers_for_controls()

    def get_worker_by_id(self, worker_id: int | None, session=None) -> ThpWorker | None:
        if not worker_id:
            return None
        return self.repository.get_worker_by_id(worker_id, session=session)

    def list_worker_role_ids(self, worker_id: int) -> list[int]:
        return self.repository.list_worker_role_ids(worker_id)

    def save_worker(self, **data) -> ThpWorker:
        worker_id = data.pop("id", None)
        role_ids = data.pop("responsibility_role_ids", None)
        data = self._normalize_worker_data(data, worker_id=worker_id)
        if role_ids is not None:
            role_ids = self._validate_role_ids(role_ids)

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

        try:
            return self.repository.save_worker(worker, role_ids=role_ids)
        except IntegrityError as error:
            number = data.get("personal_number") or ""
            detail = str(getattr(error, "orig", error)).casefold()
            if "personal_number" in detail or "uq_thp_workers_personal_number" in detail:
                raise SettingsWorkerError(
                    f"Zaměstnanec s osobním číslem „{number}“ již existuje."
                ) from error
            raise

    def _normalize_worker_data(
        self,
        data: dict,
        *,
        worker_id: int | None,
    ) -> dict:
        normalized = dict(data)
        for key in _WORKER_TEXT_FIELDS:
            if key in normalized and normalized[key] is not None:
                normalized[key] = str(normalized[key]).strip()

        if worker_id is None:
            normalized["first_name"] = self._require_name(
                normalized.get("first_name"),
                "Vyplňte jméno.",
            )
            normalized["last_name"] = self._require_name(
                normalized.get("last_name"),
                "Vyplňte příjmení.",
            )
        else:
            if "first_name" in normalized:
                normalized["first_name"] = self._require_name(
                    normalized.get("first_name"),
                    "Vyplňte jméno.",
                )
            if "last_name" in normalized:
                normalized["last_name"] = self._require_name(
                    normalized.get("last_name"),
                    "Vyplňte příjmení.",
                )

        if "personal_number" in normalized:
            number = str(normalized.get("personal_number") or "").strip()
            normalized["personal_number"] = number or None
            if number:
                self._ensure_unique_personal_number(number, exclude_worker_id=worker_id)

        if "workplace_id" in normalized:
            normalized["workplace_id"] = self._optional_workplace_id(
                normalized.get("workplace_id")
            )
        return normalized

    @staticmethod
    def _require_name(value: object, message: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise SettingsWorkerError(message)
        return normalized

    def _ensure_unique_personal_number(
        self,
        personal_number: str,
        *,
        exclude_worker_id: int | None,
    ) -> None:
        existing = self.repository.get_worker_by_personal_number(personal_number)
        if existing is None or existing.id == exclude_worker_id:
            return
        raise SettingsWorkerError(
            f"Zaměstnanec s osobním číslem „{personal_number}“ již existuje."
        )

    def _optional_workplace_id(self, workplace_id: object) -> int | None:
        if workplace_id in (None, "", 0):
            return None
        try:
            parsed = int(workplace_id)  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise SettingsWorkerError(
                "Zvolený provoz nebo pracoviště neexistuje."
            ) from error
        if self.get_workplace_by_id(parsed) is None:
            raise SettingsWorkerError("Zvolený provoz nebo pracoviště neexistuje.")
        return parsed

    def _validate_role_ids(self, role_ids: list[int]) -> list[int]:
        unique: list[int] = []
        seen: set[int] = set()
        for raw in role_ids:
            try:
                role_id = int(raw)
            except (TypeError, ValueError) as error:
                raise SettingsWorkerError(
                    "Zvolená funkce nebo role neexistuje."
                ) from error
            if role_id in seen:
                continue
            seen.add(role_id)
            if responsibility_role_service.get_by_id(role_id) is None:
                raise SettingsWorkerError("Zvolená funkce nebo role neexistuje.")
            unique.append(role_id)
        return unique

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
