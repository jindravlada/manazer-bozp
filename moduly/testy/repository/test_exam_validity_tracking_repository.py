"""Uložení vypnutého sledování platnosti. Bez řádku se kombinace sleduje."""

from dataclasses import dataclass

from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.nastaveni.modely.test_employee_central_link import TestEmployeeCentralLink
from moduly.testy.constants import (
    EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    EMPLOYEE_SOURCE_THP_WORKER,
)
from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking


@dataclass(frozen=True)
class EmployeeLinkMap:
    """Výslovná mapa z ``test_employee_central_links``. Stejné číslo samo nic nespojí."""

    worker_by_employee: dict[int, int]
    employee_by_worker: dict[int, int]


def tracking_identities(
    link_map: EmployeeLinkMap,
    employee_source: str,
    employee_id: int,
) -> tuple[tuple[str, int], ...]:
    """Identita a případný protějšek z potvrzeného propojení.

    Vrací jen dvojice zdroj a id. Číselná shoda bez řádku v mapě
    druhou osobu nepřidá.
    """
    source = employee_source or EMPLOYEE_SOURCE_TEST_EMPLOYEE
    person_id = int(employee_id)
    if source == EMPLOYEE_SOURCE_TEST_EMPLOYEE:
        worker_id = link_map.worker_by_employee.get(person_id)
        if worker_id is None:
            return ((source, person_id),)
        return (
            (EMPLOYEE_SOURCE_TEST_EMPLOYEE, person_id),
            (EMPLOYEE_SOURCE_THP_WORKER, int(worker_id)),
        )
    if source == EMPLOYEE_SOURCE_THP_WORKER:
        test_employee_id = link_map.employee_by_worker.get(person_id)
        if test_employee_id is None:
            return ((source, person_id),)
        return (
            (EMPLOYEE_SOURCE_TEST_EMPLOYEE, int(test_employee_id)),
            (EMPLOYEE_SOURCE_THP_WORKER, person_id),
        )
    return ((source, person_id),)


def load_employee_link_map(session) -> EmployeeLinkMap:
    rows = session.scalars(select(TestEmployeeCentralLink)).all()
    return EmployeeLinkMap(
        worker_by_employee={
            int(row.test_employee_id): int(row.thp_worker_id) for row in rows
        },
        employee_by_worker={
            int(row.thp_worker_id): int(row.test_employee_id) for row in rows
        },
    )


def resume_validity_tracking(
    session,
    employee_id: int,
    test_definition_id: int,
    *,
    employee_source: str = EMPLOYEE_SOURCE_TEST_EMPLOYEE,
) -> None:
    """Zruší vypnutí sledování v už otevřené transakci.

    U propojené osoby smaže značku historické i centrální identity.
    Stejné číslo jiné osoby se nesmaže.
    """
    test_id = int(test_definition_id)
    link_map = load_employee_link_map(session)
    for source, person_id in tracking_identities(link_map, employee_source, employee_id):
        session.execute(
            delete(TestExamValidityTracking).where(
                TestExamValidityTracking.employee_source == source,
                TestExamValidityTracking.employee_id == person_id,
                TestExamValidityTracking.test_definition_id == test_id,
            )
        )


class TestExamValidityTrackingRepository:
    def link_map(self) -> EmployeeLinkMap:
        with get_session() as session:
            return load_employee_link_map(session)

    def untracked_pairs(self) -> set[tuple[str, int, int]]:
        with get_session() as session:
            stmt = select(
                TestExamValidityTracking.employee_source,
                TestExamValidityTracking.employee_id,
                TestExamValidityTracking.test_definition_id,
            )
            return {
                (str(source), int(employee_id), int(test_id))
                for source, employee_id, test_id in session.execute(stmt)
            }

    def stop(
        self,
        employee_id: int,
        test_definition_id: int,
        *,
        employee_source: str = EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    ) -> None:
        test_id = int(test_definition_id)
        with get_session() as session:
            link_map = load_employee_link_map(session)
            for source, person_id in tracking_identities(
                link_map,
                employee_source,
                employee_id,
            ):
                existing = session.scalar(
                    select(TestExamValidityTracking).where(
                        TestExamValidityTracking.employee_source == source,
                        TestExamValidityTracking.employee_id == person_id,
                        TestExamValidityTracking.test_definition_id == test_id,
                    )
                )
                if existing is not None:
                    continue
                session.add(
                    TestExamValidityTracking(
                        employee_source=source,
                        employee_id=person_id,
                        test_definition_id=test_id,
                    )
                )
            session.commit()

    def resume(
        self,
        employee_id: int,
        test_definition_id: int,
        *,
        employee_source: str = EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    ) -> None:
        with get_session() as session:
            resume_validity_tracking(
                session,
                employee_id,
                test_definition_id,
                employee_source=employee_source,
            )
            session.commit()
