from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.testy.modely.test_employee_role import TestEmployeeRole


class TestEmployeeRoleRepository:
    def list_role_ids(self, employee_id: int) -> list[int]:
        with get_session() as session:
            stmt = (
                select(TestEmployeeRole.responsibility_role_id)
                .where(TestEmployeeRole.employee_id == employee_id)
                .order_by(TestEmployeeRole.sort_order, TestEmployeeRole.id)
            )
            return [int(value) for value in session.scalars(stmt)]

    def replace_roles(self, employee_id: int, role_ids: list[int]) -> None:
        with get_session() as session:
            session.execute(
                delete(TestEmployeeRole).where(
                    TestEmployeeRole.employee_id == employee_id,
                ),
            )
            for sort_order, role_id in enumerate(role_ids, start=1):
                session.add(
                    TestEmployeeRole(
                        employee_id=employee_id,
                        responsibility_role_id=role_id,
                        sort_order=sort_order,
                    ),
                )
            session.commit()
