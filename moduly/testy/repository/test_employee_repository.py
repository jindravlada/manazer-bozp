from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.testy.modely.test_employee import TestEmployee
from moduly.testy.modely.test_employee_role import TestEmployeeRole


class TestEmployeeRepository:
    def get_all(self, *, include_inactive: bool = False) -> list[TestEmployee]:
        with get_session() as session:
            stmt = select(TestEmployee)
            if not include_inactive:
                stmt = stmt.where(TestEmployee.active == True)  # noqa: E712
            employees = list(session.scalars(stmt))

        return czech_sorted(
            employees,
            key=lambda employee: (
                f"{employee.last_name}\t{employee.first_name}\t{employee.personal_number}"
            ),
        )

    def get_by_id(self, employee_id: int) -> TestEmployee | None:
        with get_session() as session:
            return session.get(TestEmployee, employee_id)

    def get_by_personal_number(self, personal_number: str) -> TestEmployee | None:
        with get_session() as session:
            stmt = select(TestEmployee).where(
                TestEmployee.personal_number == personal_number,
            )
            return session.scalar(stmt)

    def add_with_roles(
        self,
        employee: TestEmployee,
        role_ids: list[int],
    ) -> TestEmployee:
        with get_session() as session:
            session.add(employee)
            session.flush()
            for sort_order, role_id in enumerate(role_ids, start=1):
                session.add(
                    TestEmployeeRole(
                        employee_id=employee.id,
                        responsibility_role_id=role_id,
                        sort_order=sort_order,
                    ),
                )
            session.commit()
            session.refresh(employee)
            return employee

    def update(self, employee: TestEmployee) -> TestEmployee:
        with get_session() as session:
            employee = session.merge(employee)
            session.commit()
            session.refresh(employee)
            return employee
