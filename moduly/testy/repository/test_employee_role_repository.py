from sqlalchemy import select

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
