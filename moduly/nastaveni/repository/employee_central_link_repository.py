"""Úložiště výslovného propojení zaměstnanců z Testů a centrální evidence."""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from core.database.session import get_session, transaction
from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole
from moduly.nastaveni.modely.test_employee_central_link import TestEmployeeCentralLink
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.thp_worker_role import ThpWorkerRole
from moduly.nastaveni.modely.workplace import Workplace
from moduly.testy.constants import (
    EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    EMPLOYEE_SOURCE_THP_WORKER,
)
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
            "employee_source",
        }
    ),
    "test_exam_examiners": frozenset(
        {
            "id",
            "exam_id",
            "employee_id",
            "employee_source",
            "display_name",
            "role",
            "position",
        }
    ),
    "test_exam_validity_tracking": frozenset(
        {"id", "employee_id", "employee_source", "test_definition_id"}
    ),
}

_UNLINK_DEPENDENCY_MESSAGE = (
    "Propojení nelze zrušit, protože závislost převodu historických vazeb "
    "nebo nových zkoušek nelze spolehlivě ověřit."
)
_UNLINK_NEW_EXAM_MESSAGE = (
    "Propojení nelze zrušit, protože na něm závisí nová zkouška."
)
_EXAM_SOURCE_TABLES = (
    "test_exams",
    "test_exam_examiners",
    "test_exam_validity_tracking",
)

TAKEOVER_PERSONAL_NUMBER = "personal_number"
TAKEOVER_WORKPLACE = "workplace"
TAKEOVER_ROLES = "roles"
TAKEOVER_MAY_EXAMINE = "may_examine"
TAKEOVER_FIELDS = (
    TAKEOVER_PERSONAL_NUMBER,
    TAKEOVER_WORKPLACE,
    TAKEOVER_ROLES,
    TAKEOVER_MAY_EXAMINE,
)
_TAKEOVER_LABELS = {
    TAKEOVER_PERSONAL_NUMBER: "Osobní číslo",
    TAKEOVER_WORKPLACE: "Provoz",
    TAKEOVER_ROLES: "Funkce / role",
    TAKEOVER_MAY_EXAMINE: "Zkoušející / člen komise",
}
_TAKEOVER_UNCHANGED = "Beze změny"
_TAKEOVER_CONFLICT = (
    "Údaje se od přípravy návrhu změnily. Připravte nový návrh."
)


@dataclass(frozen=True)
class TakeoverFieldProposal:
    """Jedna porovnávaná položka. ``will_change`` je návrh, ne provedený zápis."""

    field: str
    label: str
    test_value: str
    central_value: str
    proposed_change: str
    will_change: bool


@dataclass(frozen=True)
class EmployeeTakeoverProposal:
    """Návrh doplnění údajů. Sám o sobě do databáze nic nezapisuje."""

    test_employee_id: int
    thp_worker_id: int
    already_linked: bool
    fields: tuple[TakeoverFieldProposal, ...]
    revision: str


@dataclass(frozen=True)
class EmployeeTakeoverResult:
    """Výsledek potvrzeného převzetí. ``linked_now`` je ano jen u nové vazby."""

    link_id: int
    test_employee_id: int
    thp_worker_id: int
    linked_now: bool
    applied_fields: tuple[str, ...]


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
            self._assert_unlink_has_no_unknown_dependency(
                session,
                test_employee_id=test_employee_id,
                thp_worker_id=thp_worker_id,
            )
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

    def propose_takeover(
        self,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> EmployeeTakeoverProposal:
        """Porovná vybranou dvojici. Osobní číslo ani jméno nikoho nespáruje."""
        with get_session() as session:
            employee = self._require_employee(session, test_employee_id)
            worker = self._require_worker(session, thp_worker_id)
            snapshot = self._takeover_snapshot(session, employee, worker)
            return self._proposal_from_snapshot(
                session,
                employee=employee,
                worker=worker,
                snapshot=snapshot,
            )

    def apply_confirmed_takeover(
        self,
        *,
        test_employee_id: int,
        thp_worker_id: int,
        revision: str,
        confirm_fields: list[str],
    ) -> EmployeeTakeoverResult:
        """Propojí dvojici a zapíše jen potvrzené doplnění, v jedné transakci.

        Před zápisem znovu sestaví návrh. Když se porovnávané údaje mezitím
        změnily, nic neuloží a vyžádá nový návrh. Existující vazbu této
        dvojice znovu nezakládá.
        """
        confirmed = self._confirmed_fields(confirm_fields)
        with transaction() as session:
            employee = self._require_employee(session, test_employee_id)
            worker = self._require_worker(session, thp_worker_id)
            snapshot = self._takeover_snapshot(session, employee, worker)
            if self._revision(snapshot) != revision:
                raise EmployeeLinkError(_TAKEOVER_CONFLICT)
            link, linked_now = self._ensure_pair_link(
                session,
                test_employee_id=test_employee_id,
                thp_worker_id=thp_worker_id,
            )
            applied = self._apply_confirmed_fields(
                session,
                worker=worker,
                snapshot=snapshot,
                confirmed=confirmed,
            )
            self._after_takeover_writes(session)
            session.flush()
            return EmployeeTakeoverResult(
                link_id=int(link.id),
                test_employee_id=int(link.test_employee_id),
                thp_worker_id=int(link.thp_worker_id),
                linked_now=linked_now,
                applied_fields=tuple(applied),
            )

    def _after_takeover_writes(self, session: Session) -> None:
        """Poslední krok transakce. Test jím ověří návrat při chybě."""
        return None

    def _confirmed_fields(self, confirm_fields: list[str]) -> list[str]:
        unknown = [field for field in confirm_fields if field not in TAKEOVER_FIELDS]
        if unknown:
            raise EmployeeLinkError("Neznámá položka návrhu.")
        ordered = []
        for field in TAKEOVER_FIELDS:
            if field in confirm_fields and field not in ordered:
                ordered.append(field)
        return ordered

    def _ensure_pair_link(
        self,
        session: Session,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> tuple[TestEmployeeCentralLink, bool]:
        by_employee = self._link_for_employee(session, test_employee_id)
        by_worker = self._link_for_worker(session, thp_worker_id)
        if (
            by_employee is not None
            and by_worker is not None
            and by_employee.id == by_worker.id
        ):
            return by_employee, False
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
        return link, True

    def _apply_confirmed_fields(
        self,
        session: Session,
        *,
        worker: ThpWorker,
        snapshot: dict,
        confirmed: list[str],
    ) -> list[str]:
        applied: list[str] = []
        if TAKEOVER_PERSONAL_NUMBER in confirmed and self._number_can_copy(snapshot):
            number = str(snapshot["test"]["personal_number"])
            clash = session.scalar(
                select(ThpWorker).where(
                    ThpWorker.personal_number == number,
                    ThpWorker.id != worker.id,
                )
            )
            if clash is not None:
                raise EmployeeLinkError(
                    "Zaměstnanec s osobním číslem "
                    f"„{number}“ již existuje v centrální evidenci. "
                    "Připravte nový návrh."
                )
            worker.personal_number = number
            applied.append(TAKEOVER_PERSONAL_NUMBER)
        if TAKEOVER_WORKPLACE in confirmed and snapshot["central"]["workplace_id"] is None:
            workplace_id = snapshot["test"]["workplace_id"]
            if workplace_id is not None:
                if session.get(Workplace, workplace_id) is None:
                    raise EmployeeLinkError(
                        "Zvolený provoz nebo pracoviště neexistuje."
                    )
                worker.workplace_id = int(workplace_id)
                applied.append(TAKEOVER_WORKPLACE)
        if TAKEOVER_ROLES in confirmed:
            added = self._add_missing_roles(
                session,
                worker_id=int(worker.id),
                test_roles=snapshot["test"]["roles"],
                central_roles=snapshot["central"]["roles"],
            )
            if added:
                applied.append(TAKEOVER_ROLES)
        if (
            TAKEOVER_MAY_EXAMINE in confirmed
            and snapshot["test"]["may_examine"]
            and not snapshot["central"]["may_examine"]
        ):
            worker.may_examine = True
            applied.append(TAKEOVER_MAY_EXAMINE)
        return applied

    def _add_missing_roles(
        self,
        session: Session,
        *,
        worker_id: int,
        test_roles: list[dict],
        central_roles: list[dict],
    ) -> bool:
        present = {int(row["role_id"]) for row in central_roles}
        orders = [int(row["sort_order"]) for row in central_roles]
        next_order = max(orders) + 1 if orders else 0
        added = False
        for row in test_roles:
            role_id = int(row["role_id"])
            if role_id in present:
                continue
            if session.get(ResponsibilityRole, role_id) is None:
                raise EmployeeLinkError("Zvolená funkce nebo role neexistuje.")
            session.add(
                ThpWorkerRole(
                    thp_worker_id=worker_id,
                    responsibility_role_id=role_id,
                    sort_order=next_order,
                )
            )
            present.add(role_id)
            next_order += 1
            added = True
        return added

    def _takeover_snapshot(
        self,
        session: Session,
        employee: TestEmployee,
        worker: ThpWorker,
    ) -> dict:
        employee_link = self._link_for_employee(session, int(employee.id))
        worker_link = self._link_for_worker(session, int(worker.id))
        return {
            "test": {
                "personal_number": str(employee.personal_number or "").strip(),
                "workplace_id": (
                    int(employee.workplace_id)
                    if employee.workplace_id is not None
                    else None
                ),
                "roles": self._role_snapshot(
                    session,
                    TestEmployeeRole,
                    TestEmployeeRole.employee_id == employee.id,
                    TestEmployeeRole.sort_order,
                    TestEmployeeRole.id,
                ),
                "may_examine": bool(employee.may_examine),
            },
            "central": {
                "personal_number": str(worker.personal_number or "").strip(),
                "workplace_id": (
                    int(worker.workplace_id)
                    if worker.workplace_id is not None
                    else None
                ),
                "roles": self._role_snapshot(
                    session,
                    ThpWorkerRole,
                    ThpWorkerRole.thp_worker_id == worker.id,
                    ThpWorkerRole.sort_order,
                    ThpWorkerRole.id,
                ),
                "may_examine": bool(worker.may_examine),
            },
            "employee_link_worker_id": (
                int(employee_link.thp_worker_id) if employee_link is not None else None
            ),
            "worker_link_employee_id": (
                int(worker_link.test_employee_id) if worker_link is not None else None
            ),
        }

    def _role_snapshot(self, session: Session, model, criterion, sort_column, id_column):
        rows = session.scalars(
            select(model).where(criterion).order_by(sort_column, id_column)
        )
        return [
            {
                "role_id": int(row.responsibility_role_id),
                "sort_order": int(row.sort_order),
            }
            for row in rows
        ]

    def _proposal_from_snapshot(
        self,
        session: Session,
        *,
        employee: TestEmployee,
        worker: ThpWorker,
        snapshot: dict,
    ) -> EmployeeTakeoverProposal:
        same_link = (
            snapshot["employee_link_worker_id"] == int(worker.id)
            and snapshot["worker_link_employee_id"] == int(employee.id)
        )
        fields = (
            self._number_proposal(snapshot),
            self._workplace_proposal(session, snapshot),
            self._roles_proposal(session, snapshot),
            self._examiner_proposal(snapshot),
        )
        return EmployeeTakeoverProposal(
            test_employee_id=int(employee.id),
            thp_worker_id=int(worker.id),
            already_linked=same_link,
            fields=fields,
            revision=self._revision(snapshot),
        )

    def _number_proposal(self, snapshot: dict) -> TakeoverFieldProposal:
        test_number = snapshot["test"]["personal_number"]
        central_number = snapshot["central"]["personal_number"]
        will_change = bool(test_number) and not central_number
        return self._field_proposal(
            TAKEOVER_PERSONAL_NUMBER,
            self._text_or_dash(test_number),
            self._text_or_dash(central_number),
            f"Doplnit {test_number}" if will_change else _TAKEOVER_UNCHANGED,
            will_change,
        )

    def _workplace_proposal(self, session: Session, snapshot: dict) -> TakeoverFieldProposal:
        test_id = snapshot["test"]["workplace_id"]
        central_id = snapshot["central"]["workplace_id"]
        will_change = central_id is None and test_id is not None
        test_name = self._workplace_name(session, test_id)
        central_name = self._workplace_name(session, central_id)
        change = (
            f"Přiřadit {test_name}" if will_change and test_name else _TAKEOVER_UNCHANGED
        )
        if will_change and not test_name:
            will_change = False
        return self._field_proposal(
            TAKEOVER_WORKPLACE,
            test_name or "—",
            central_name or "—",
            change,
            will_change,
        )

    def _roles_proposal(self, session: Session, snapshot: dict) -> TakeoverFieldProposal:
        test_roles = snapshot["test"]["roles"]
        central_ids = {int(row["role_id"]) for row in snapshot["central"]["roles"]}
        missing = [row for row in test_roles if int(row["role_id"]) not in central_ids]
        missing_names = [
            name
            for row in missing
            if (name := self._role_name(session, int(row["role_id"])))
        ]
        will_change = bool(missing_names)
        return self._field_proposal(
            TAKEOVER_ROLES,
            self._role_list_text(session, test_roles),
            self._role_list_text(session, snapshot["central"]["roles"]),
            "Doplnit " + ", ".join(missing_names) if will_change else _TAKEOVER_UNCHANGED,
            will_change,
        )

    def _examiner_proposal(self, snapshot: dict) -> TakeoverFieldProposal:
        test_flag = bool(snapshot["test"]["may_examine"])
        central_flag = bool(snapshot["central"]["may_examine"])
        will_change = test_flag and not central_flag
        return self._field_proposal(
            TAKEOVER_MAY_EXAMINE,
            "Ano" if test_flag else "Ne",
            "Ano" if central_flag else "Ne",
            "Zapnout" if will_change else _TAKEOVER_UNCHANGED,
            will_change,
        )

    def _field_proposal(
        self,
        field: str,
        test_value: str,
        central_value: str,
        proposed_change: str,
        will_change: bool,
    ) -> TakeoverFieldProposal:
        return TakeoverFieldProposal(
            field=field,
            label=_TAKEOVER_LABELS[field],
            test_value=test_value,
            central_value=central_value,
            proposed_change=proposed_change,
            will_change=will_change,
        )

    def _workplace_name(self, session: Session, workplace_id: int | None) -> str:
        if workplace_id is None:
            return ""
        workplace = session.get(Workplace, int(workplace_id))
        if workplace is None:
            return ""
        return str(workplace.name or "").strip()

    def _role_name(self, session: Session, role_id: int) -> str:
        role = session.get(ResponsibilityRole, role_id)
        if role is None:
            return ""
        return str(role.name or "").strip()

    def _role_list_text(self, session: Session, roles: list[dict]) -> str:
        names = [
            name
            for row in roles
            if (name := self._role_name(session, int(row["role_id"])))
        ]
        return ", ".join(names) if names else "—"

    def _text_or_dash(self, value: str) -> str:
        text_value = str(value or "").strip()
        return text_value or "—"

    def _number_can_copy(self, snapshot: dict) -> bool:
        return bool(snapshot["test"]["personal_number"]) and not snapshot["central"][
            "personal_number"
        ]

    def _revision(self, snapshot: dict) -> str:
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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

    def _assert_unlink_has_no_unknown_dependency(
        self,
        session: Session,
        *,
        test_employee_id: int,
        thp_worker_id: int,
    ) -> None:
        """Zrušení projde jen u známého schématu a bez nové zkoušky této dvojice.

        Sloupec ``employee_source`` je známý. Hodnota ``test_employee`` patří
        k historickým zkouškám a zrušení mapy nebrání. Řádek ``thp_worker``
        u tohoto zaměstnance už je nová zkouška, proto se vazba neruší.
        Neznámý sloupec nebo nepovolený zdroj ověřit nejde, proto se zrušení
        odmítne.
        """
        for table_name, known in _UNLINK_KNOWN_COLUMNS.items():
            live = self._live_columns(session, table_name)
            if live is None or live != known:
                raise EmployeeLinkError(_UNLINK_DEPENDENCY_MESSAGE)
        for table_name in _EXAM_SOURCE_TABLES:
            invalid = session.execute(
                text(
                    f'SELECT COUNT(*) FROM "{table_name}" '
                    "WHERE employee_source IS NULL "
                    "OR employee_source NOT IN (:historical, :central)"
                ),
                {
                    "historical": EMPLOYEE_SOURCE_TEST_EMPLOYEE,
                    "central": EMPLOYEE_SOURCE_THP_WORKER,
                },
            ).scalar()
            if int(invalid or 0) > 0:
                raise EmployeeLinkError(_UNLINK_DEPENDENCY_MESSAGE)
            dependent = session.execute(
                text(
                    f'SELECT COUNT(*) FROM "{table_name}" '
                    "WHERE employee_source = :central "
                    "AND employee_id IN (:worker_id, :test_employee_id)"
                ),
                {
                    "central": EMPLOYEE_SOURCE_THP_WORKER,
                    "worker_id": int(thp_worker_id),
                    "test_employee_id": int(test_employee_id),
                },
            ).scalar()
            if int(dependent or 0) > 0:
                raise EmployeeLinkError(_UNLINK_NEW_EXAM_MESSAGE)

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
