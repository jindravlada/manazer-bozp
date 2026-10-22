"""Úložiště výslovného propojení zaměstnanců z Testů a centrální evidence."""

from dataclasses import dataclass

from sqlalchemy import delete, select, text
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


@dataclass(frozen=True)
class EmployeeUnlinkResult:
    """Výsledek zrušení propojení. ``removed`` je ne, když dvojice v mapě není."""

    removed: bool
    message: str


# Sloupce, které dnes nenesou převod zkoušek na centrálního zaměstnance.
# Cokoli navíc může být dokončený převod nebo nová závislost, kterou tento
# kód neumí vyhodnotit. Pak se propojení nesmí zrušit.
_UNLINK_KNOWN_COLUMNS: dict[str, frozenset[str]] = {
    "test_employee_central_links": frozenset(
        {"id", "test_employee_id", "thp_worker_id", "created_at"}
    ),
    "test_exams": frozenset(
        {
            "id",
            "employee_id",
            "test_definition_id",
            "exam_date",
            "valid_until",
            "status",
            "examiner_mode",
            "created_at",
            "employee_personal_number",
            "employee_first_name",
            "employee_last_name",
            "employee_title_before",
            "employee_title_after",
            "employee_display_name",
            "employee_workplace_name",
            "employee_roles_text",
            "test_name",
            "uses_written",
            "uses_oral",
            "allowed_wrong_answers",
            "seconds_per_question",
            "written_duration_seconds",
            "validity_value",
            "validity_unit",
            "written_started_at",
            "written_time_mark",
            "written_finished_at",
            "written_finish_reason",
            "written_question_count",
            "written_correct_count",
            "written_incorrect_count",
            "written_unanswered_count",
            "written_allowed_wrong_answers",
            "written_result",
            "exam_result",
            "written_evaluated_at",
            "oral_failed_at",
            "written_mode",
            "signed_protocol_attachment_id",
            "written_technical_detail",
        }
    ),
    "test_exam_examiners": frozenset(
        {"id", "exam_id", "employee_id", "display_name", "role", "position"}
    ),
    "test_exam_validity_tracking": frozenset(
        {"id", "employee_id", "test_definition_id"}
    ),
}

_UNLINK_DEPENDENCY_MESSAGE = (
    "Propojení nelze zrušit, protože závislost převodu historických vazeb "
    "nebo nových zkoušek nelze spolehlivě ověřit."
)


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

    def unlink(
        self,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> EmployeeUnlinkResult:
        with transaction() as session:
            by_employee = self._link_for_employee(session, test_employee_id)
            by_worker = self._link_for_worker(session, thp_worker_id)
            if by_employee is None and by_worker is None:
                return EmployeeUnlinkResult(
                    removed=False,
                    message="Propojení mezi těmito zaměstnanci neexistuje.",
                )
            if (
                by_employee is None
                or by_worker is None
                or by_employee.id != by_worker.id
            ):
                raise EmployeeLinkError(
                    "Požadovaná dvojice neodpovídá uloženému propojení."
                )
            self._assert_unlink_has_no_unknown_dependency(session)
            self._delete_link(
                session,
                by_employee,
                test_employee_id=test_employee_id,
                thp_worker_id=thp_worker_id,
            )
            return EmployeeUnlinkResult(
                removed=True,
                message="Propojení bylo zrušeno.",
            )

    def _delete_link(
        self,
        session: Session,
        link: TestEmployeeCentralLink,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> None:
        result = session.execute(
            delete(TestEmployeeCentralLink).where(
                TestEmployeeCentralLink.id == link.id,
                TestEmployeeCentralLink.test_employee_id == test_employee_id,
                TestEmployeeCentralLink.thp_worker_id == thp_worker_id,
            )
        )
        if result.rowcount != 1:
            raise EmployeeLinkError(
                "Propojení mezi těmito zaměstnanci neexistuje."
            )

    def _assert_unlink_has_no_unknown_dependency(self, session: Session) -> None:
        """Zrušení projde jen u známého schématu bez sloupců převodu zkoušek.

        Historické zkoušky dál ukazují na ``test_employees`` a mapa na ně
        neodkazuje. Nový sloupec v mapě nebo ve zkouškách by mohl znamenat
        dokončený převod. Ten tento kód nečte, proto zrušení odmítne.
        """
        for table_name, known in _UNLINK_KNOWN_COLUMNS.items():
            live = self._live_columns(session, table_name)
            if live is None or live != known:
                raise EmployeeLinkError(_UNLINK_DEPENDENCY_MESSAGE)

    def _live_columns(self, session: Session, table_name: str) -> set[str] | None:
        exists = session.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = :table_name"
            ),
            {"table_name": table_name},
        ).first()
        if exists is None:
            return None
        info = session.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
        return {str(column[1]) for column in info}

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
