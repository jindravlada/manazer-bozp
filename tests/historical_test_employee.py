"""Syntetický historický zaměstnanec v ``test_employees`` jen pro testy.

Produkční kód do původní evidence nezapisuje. Testy historické
kompatibility si řádek založí přímo, mimo službu modulu.
"""

from __future__ import annotations

from datetime import datetime


def _normalize(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _unique_role_ids(role_ids: list[int]) -> list[int]:
    unique: list[int] = []
    seen: set[int] = set()
    for raw in role_ids:
        role_id = int(raw)
        if role_id in seen:
            continue
        seen.add(role_id)
        unique.append(role_id)
    return unique


def seed_historical_test_employee(
    *,
    personal_number: str,
    first_name: str,
    last_name: str,
    workplace_id: int,
    responsibility_role_ids: list[int],
    active: bool = True,
    title_before: str = "",
    title_after: str = "",
    may_examine: bool = False,
):
    from core.database.session import get_session
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole

    now = datetime.now()
    employee = TestEmployee(
        personal_number=_normalize(personal_number),
        first_name=_normalize(first_name),
        last_name=_normalize(last_name),
        title_before=_normalize(title_before),
        title_after=_normalize(title_after),
        workplace_id=int(workplace_id),
        may_examine=bool(may_examine),
        active=bool(active),
        created_at=now,
        updated_at=now,
    )
    with get_session() as session:
        session.add(employee)
        session.flush()
        for sort_order, role_id in enumerate(
            _unique_role_ids(responsibility_role_ids),
            start=1,
        ):
            session.add(
                TestEmployeeRole(
                    employee_id=employee.id,
                    responsibility_role_id=role_id,
                    sort_order=sort_order,
                )
            )
        session.commit()
        session.refresh(employee)
        session.expunge(employee)
        return employee


def set_historical_test_employee_active(employee_id: int, *, active: bool):
    from core.database.session import get_session
    from moduly.testy.modely.test_employee import TestEmployee

    with get_session() as session:
        employee = session.get(TestEmployee, employee_id)
        if employee is None:
            raise LookupError(employee_id)
        employee.active = bool(active)
        employee.updated_at = datetime.now()
        session.commit()
        session.refresh(employee)
        session.expunge(employee)
        return employee


def update_historical_test_employee(
    employee_id: int,
    *,
    personal_number: str,
    first_name: str,
    last_name: str,
    workplace_id: int | None,
    responsibility_role_ids: list[int] | None,
    active: bool,
    title_before: str = "",
    title_after: str = "",
    may_examine: bool = False,
):
    from sqlalchemy import delete

    from core.database.session import get_session
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole

    with get_session() as session:
        employee = session.get(TestEmployee, employee_id)
        if employee is None:
            raise LookupError(employee_id)
        employee.personal_number = _normalize(personal_number)
        employee.first_name = _normalize(first_name)
        employee.last_name = _normalize(last_name)
        employee.title_before = _normalize(title_before)
        employee.title_after = _normalize(title_after)
        employee.workplace_id = int(workplace_id)
        employee.may_examine = bool(may_examine)
        employee.active = bool(active)
        employee.updated_at = datetime.now()
        session.execute(
            delete(TestEmployeeRole).where(TestEmployeeRole.employee_id == employee.id)
        )
        for sort_order, role_id in enumerate(
            _unique_role_ids(list(responsibility_role_ids or [])),
            start=1,
        ):
            session.add(
                TestEmployeeRole(
                    employee_id=employee.id,
                    responsibility_role_id=role_id,
                    sort_order=sort_order,
                )
            )
        session.commit()
        session.refresh(employee)
        session.expunge(employee)
        return employee
