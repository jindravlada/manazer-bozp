"""Uložení vypnutého sledování platnosti. Bez řádku se kombinace sleduje."""

from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking


def resume_validity_tracking(session, employee_id: int, test_definition_id: int) -> None:
    """Zruší vypnutí sledování v už otevřené transakci."""
    session.execute(
        delete(TestExamValidityTracking).where(
            TestExamValidityTracking.employee_id == int(employee_id),
            TestExamValidityTracking.test_definition_id == int(test_definition_id),
        )
    )


class TestExamValidityTrackingRepository:
    def untracked_pairs(self) -> set[tuple[int, int]]:
        with get_session() as session:
            stmt = select(
                TestExamValidityTracking.employee_id,
                TestExamValidityTracking.test_definition_id,
            )
            return {
                (int(employee_id), int(test_id))
                for employee_id, test_id in session.execute(stmt)
            }

    def stop(self, employee_id: int, test_definition_id: int) -> None:
        employee = int(employee_id)
        test_id = int(test_definition_id)
        with get_session() as session:
            stmt = select(TestExamValidityTracking).where(
                TestExamValidityTracking.employee_id == employee,
                TestExamValidityTracking.test_definition_id == test_id,
            )
            if session.scalar(stmt) is not None:
                return
            session.add(
                TestExamValidityTracking(
                    employee_id=employee,
                    test_definition_id=test_id,
                )
            )
            session.commit()

    def resume(self, employee_id: int, test_definition_id: int) -> None:
        with get_session() as session:
            resume_validity_tracking(session, employee_id, test_definition_id)
            session.commit()
