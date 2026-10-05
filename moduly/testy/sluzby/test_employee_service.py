"""Evidence zaměstnanců pro přezkušování."""

from __future__ import annotations

from datetime import datetime

from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.modely.test_employee import TestEmployee
from moduly.testy.repository.test_employee_repository import TestEmployeeRepository
from moduly.testy.repository.test_employee_role_repository import (
    TestEmployeeRoleRepository,
)


class TestEmployeeError(ValueError):
    pass


def normalize_personal_number(value: str) -> str:
    """Sjednotí osobní číslo pro uložení i pozdější párování při importu."""
    return " ".join(str(value or "").strip().split())


class TestEmployeeService:
    def __init__(self) -> None:
        self.repository = TestEmployeeRepository()
        self.roles_repository = TestEmployeeRoleRepository()

    def create_employee(
        self,
        *,
        personal_number: str,
        first_name: str,
        last_name: str,
        workplace_id: int,
        responsibility_role_ids: list[int],
        active: bool = True,
    ) -> TestEmployee:
        number = self._validate_personal_number(personal_number)
        self._ensure_unique_personal_number(number)
        first = self._validate_name(first_name, "Vyplňte jméno.")
        last = self._validate_name(last_name, "Vyplňte příjmení.")
        workplace = self._require_workplace(workplace_id)
        role_ids = self._require_roles(responsibility_role_ids)

        employee = TestEmployee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=workplace,
            active=bool(active),
        )
        return self.repository.add_with_roles(employee, role_ids)

    def get_employee(self, employee_id: int | None) -> TestEmployee | None:
        if not employee_id:
            return None
        return self.repository.get_by_id(employee_id)

    def get_by_personal_number(self, personal_number: str) -> TestEmployee | None:
        number = normalize_personal_number(personal_number)
        if not number:
            return None
        return self.repository.get_by_personal_number(number)

    def list_employees(self, *, include_inactive: bool = False) -> list[TestEmployee]:
        return self.repository.get_all(include_inactive=include_inactive)

    def update_employee(
        self,
        employee_id: int,
        *,
        personal_number: str,
        first_name: str,
        last_name: str,
    ) -> TestEmployee:
        employee = self._require_employee(employee_id)
        number = self._validate_personal_number(personal_number)
        self._ensure_unique_personal_number(number, exclude_employee_id=employee_id)
        employee.personal_number = number
        employee.first_name = self._validate_name(first_name, "Vyplňte jméno.")
        employee.last_name = self._validate_name(last_name, "Vyplňte příjmení.")
        employee.updated_at = datetime.now()
        return self.repository.update(employee)

    def set_active(self, employee_id: int, *, active: bool) -> TestEmployee:
        employee = self._require_employee(employee_id)
        employee.active = bool(active)
        employee.updated_at = datetime.now()
        return self.repository.update(employee)

    def activate(self, employee_id: int) -> TestEmployee:
        return self.set_active(employee_id, active=True)

    def deactivate(self, employee_id: int) -> TestEmployee:
        return self.set_active(employee_id, active=False)

    def set_workplace(self, employee_id: int, workplace_id: int) -> TestEmployee:
        employee = self._require_employee(employee_id)
        employee.workplace_id = self._require_workplace(workplace_id)
        employee.updated_at = datetime.now()
        return self.repository.update(employee)

    def get_role_ids(self, employee_id: int) -> list[int]:
        self._require_employee(employee_id)
        return self.roles_repository.list_role_ids(employee_id)

    def set_roles(self, employee_id: int, responsibility_role_ids: list[int]) -> list[int]:
        self._require_employee(employee_id)
        role_ids = self._require_roles(responsibility_role_ids)
        self.roles_repository.replace_roles(employee_id, role_ids)
        employee = self._require_employee(employee_id)
        employee.updated_at = datetime.now()
        self.repository.update(employee)
        return role_ids

    def _require_employee(self, employee_id: int) -> TestEmployee:
        employee = self.repository.get_by_id(employee_id)
        if employee is None:
            raise TestEmployeeError("Zaměstnanec nebyl nalezen.")
        return employee

    def _validate_personal_number(self, personal_number: str) -> str:
        number = normalize_personal_number(personal_number)
        if not number:
            raise TestEmployeeError("Vyplňte osobní číslo.")
        return number

    def _validate_name(self, value: str, message: str) -> str:
        normalized = " ".join(str(value or "").strip().split())
        if not normalized:
            raise TestEmployeeError(message)
        return normalized

    def _ensure_unique_personal_number(
        self,
        personal_number: str,
        *,
        exclude_employee_id: int | None = None,
    ) -> None:
        existing = self.repository.get_by_personal_number(personal_number)
        if existing is None or existing.id == exclude_employee_id:
            return
        raise TestEmployeeError(
            f"Zaměstnanec s osobním číslem „{personal_number}“ již existuje."
        )

    def _require_workplace(self, workplace_id: int | None) -> int:
        if not workplace_id:
            raise TestEmployeeError("Zvolte provoz nebo pracoviště.")
        workplace = settings_service.get_workplace_by_id(int(workplace_id))
        if workplace is None:
            raise TestEmployeeError("Zvolený provoz nebo pracoviště neexistuje.")
        return int(workplace.id)

    def _require_roles(self, role_ids: list[int] | None) -> list[int]:
        if not role_ids:
            raise TestEmployeeError("Přiřaďte alespoň jednu funkci nebo roli.")
        unique: list[int] = []
        seen: set[int] = set()
        for raw in role_ids:
            role_id = int(raw)
            if role_id in seen:
                continue
            seen.add(role_id)
            if responsibility_role_service.get_by_id(role_id) is None:
                raise TestEmployeeError("Zvolená funkce nebo role neexistuje.")
            unique.append(role_id)
        return unique


test_employee_service = TestEmployeeService()
