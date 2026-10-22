"""Čtení historické evidence zaměstnanců pro přezkušování.

Nové osoby se zakládají v centrální evidenci. Tato služba historické
řádky v ``test_employees`` nevytváří ani nemění.
"""

from __future__ import annotations

from moduly.testy.modely.test_employee import TestEmployee
from moduly.testy.repository.test_employee_repository import TestEmployeeRepository
from moduly.testy.repository.test_employee_role_repository import (
    TestEmployeeRoleRepository,
)


def normalize_personal_number(value: str) -> str:
    """Sjednotí osobní číslo pro vyhledání historického záznamu."""
    return " ".join(str(value or "").strip().split())


class TestEmployeeService:
    def __init__(self) -> None:
        self.repository = TestEmployeeRepository()
        self.roles_repository = TestEmployeeRoleRepository()

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

    def list_eligible_examiners(self) -> list[TestEmployee]:
        """Aktivní historičtí zaměstnanci s oprávněním zkoušet."""
        return [
            employee
            for employee in self.repository.get_all(include_inactive=False)
            if employee.may_examine
        ]

    def get_role_ids(self, employee_id: int) -> list[int]:
        return self.roles_repository.list_role_ids(employee_id)


test_employee_service = TestEmployeeService()
