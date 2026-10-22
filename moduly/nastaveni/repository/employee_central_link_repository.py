"""Úložiště výslovného propojení zaměstnanců z Testů a centrální evidence."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session, transaction
from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole
from moduly.nastaveni.modely.test_employee_central_link import TestEmployeeCentralLink
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.thp_worker_role import ThpWorkerRole
from moduly.nastaveni.modely.workplace import Workplace
from moduly.testy.modely.test_employee import TestEmployee
from moduly.testy.modely.test_employee_role import TestEmployeeRole


class EmployeeLinkError(ValueError):
    pass


class EmployeeCentralLinkRepository:
    def get_by_test_employee(
        self,
        test_employee_id: int,
    ) -> TestEmployeeCentralLink | None:
        with get_session() as session:
            link = session.scalar(
                select(TestEmployeeCentralLink).where(
                    TestEmployeeCentralLink.test_employee_id == test_employee_id
                )
            )
            if link is not None:
                session.expunge(link)
            return link

    def get_by_worker(self, thp_worker_id: int) -> TestEmployeeCentralLink | None:
        with get_session() as session:
            link = session.scalar(
                select(TestEmployeeCentralLink).where(
                    TestEmployeeCentralLink.thp_worker_id == thp_worker_id
                )
            )
            if link is not None:
                session.expunge(link)
            return link

    def personal_number_hints(self, test_employee_id: int) -> list[ThpWorker]:
        """Shoda osobního čísla jen ke čtení. Propojení ani údaje nemění."""
        with get_session() as session:
            employee = session.get(TestEmployee, test_employee_id)
            if employee is None:
                raise EmployeeLinkError("Zaměstnanec z Testů nebyl nalezen.")
            number = str(employee.personal_number or "").strip()
            if not number:
                return []
            workers = list(
                session.scalars(
                    select(ThpWorker).where(ThpWorker.personal_number == number)
                )
            )
            for worker in workers:
                session.expunge(worker)
            return workers

    def link_existing(
        self,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> TestEmployeeCentralLink:
        with transaction() as session:
            self._require_employee(session, test_employee_id)
            self._require_worker(session, thp_worker_id)
            by_employee = self._link_for_employee(session, test_employee_id)
            by_worker = self._link_for_worker(session, thp_worker_id)
            if (
                by_employee is not None
                and by_worker is not None
                and by_employee.id == by_worker.id
            ):
                session.expunge(by_employee)
                return by_employee
            if by_employee is not None:
                raise EmployeeLinkError(
                    "Zaměstnanec z Testů je již propojen s jiným zaměstnancem."
                )
            if by_worker is not None:
                raise EmployeeLinkError(
                    "Centrální zaměstnanec je již propojen s jiným zaměstnancem z Testů."
                )
            link = TestEmployeeCentralLink(
                test_employee_id=test_employee_id,
                thp_worker_id=thp_worker_id,
            )
            self._add_link(session, link)
            session.flush()
            session.refresh(link)
            session.expunge(link)
            return link

    def create_and_link(self, test_employee_id: int) -> TestEmployeeCentralLink:
        with transaction() as session:
            employee = self._require_employee(session, test_employee_id)
            if self._link_for_employee(session, test_employee_id) is not None:
                raise EmployeeLinkError("Zaměstnanec z Testů je již propojen.")

            workplace = session.get(Workplace, employee.workplace_id)
            if workplace is None:
                raise EmployeeLinkError(
                    "Zvolený provoz nebo pracoviště neexistuje."
                )

            role_rows = list(
                session.scalars(
                    select(TestEmployeeRole)
                    .where(TestEmployeeRole.employee_id == employee.id)
                    .order_by(TestEmployeeRole.sort_order, TestEmployeeRole.id)
                )
            )
            for row in role_rows:
                if session.get(ResponsibilityRole, row.responsibility_role_id) is None:
                    raise EmployeeLinkError("Zvolená funkce nebo role neexistuje.")

            number = str(employee.personal_number or "").strip()
            if number:
                clash = session.scalar(
                    select(ThpWorker).where(ThpWorker.personal_number == number)
                )
                if clash is not None:
                    raise EmployeeLinkError(
                        "Zaměstnanec s osobním číslem "
                        f"„{number}“ již existuje v centrální evidenci."
                    )

            worker = ThpWorker(
                title_before=employee.title_before or "",
                first_name=employee.first_name,
                last_name=employee.last_name,
                title_after=employee.title_after or "",
                position="",
                phone="",
                email="",
                personal_number=number or None,
                workplace_id=int(employee.workplace_id),
                is_thp=False,
                may_examine=bool(employee.may_examine),
                active=bool(employee.active),
                performs_controls=False,
            )
            session.add(worker)
            session.flush()
            for row in role_rows:
                session.add(
                    ThpWorkerRole(
                        thp_worker_id=worker.id,
                        responsibility_role_id=int(row.responsibility_role_id),
                        sort_order=int(row.sort_order),
                    )
                )
            link = TestEmployeeCentralLink(
                test_employee_id=employee.id,
                thp_worker_id=worker.id,
            )
            self._add_link(session, link)
            session.flush()
            session.refresh(link)
            session.expunge(link)
            return link

    def _add_link(self, session: Session, link: TestEmployeeCentralLink) -> None:
        session.add(link)

    def _require_employee(self, session: Session, test_employee_id: int) -> TestEmployee:
        employee = session.get(TestEmployee, test_employee_id)
        if employee is None:
            raise EmployeeLinkError("Zaměstnanec z Testů nebyl nalezen.")
        return employee

    def _require_worker(self, session: Session, thp_worker_id: int) -> ThpWorker:
        worker = session.get(ThpWorker, thp_worker_id)
        if worker is None:
            raise EmployeeLinkError(
                "Zaměstnanec v centrální evidenci nebyl nalezen."
            )
        return worker

    def _link_for_employee(
        self,
        session: Session,
        test_employee_id: int,
    ) -> TestEmployeeCentralLink | None:
        return session.scalar(
            select(TestEmployeeCentralLink).where(
                TestEmployeeCentralLink.test_employee_id == test_employee_id
            )
        )

    def _link_for_worker(
        self,
        session: Session,
        thp_worker_id: int,
    ) -> TestEmployeeCentralLink | None:
        return session.scalar(
            select(TestEmployeeCentralLink).where(
                TestEmployeeCentralLink.thp_worker_id == thp_worker_id
            )
        )
