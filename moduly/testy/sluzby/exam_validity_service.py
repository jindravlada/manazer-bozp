"""Evidenční přehled platnosti skutečně založených zkoušek.

Nevytváří povinné testy ani nemění uložený výsledek zkoušky.
Platnost se odvozuje z poslední úspěšně dokončené zkoušky dané
kombinace zaměstnanec × test. Zaměstnanec je zdroj a id. Propojená
osoba z mapy má pro jeden test jeden řádek.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from core.utils.czech_sort import czech_sort_key
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.constants import (
    EXAM_STATUS_CANCELLED,
    EXAM_STATUS_COMPLETED,
    EXAM_STATUS_PREPARED,
    EXAM_STATUS_STARTED,
    EXAM_VALIDITY_STATE_EXPIRED,
    EXAM_VALIDITY_STATE_EXPIRING,
    EXAM_VALIDITY_STATE_NO_SUCCESS,
    EXAM_VALIDITY_STATE_UNLIMITED,
    EXAM_VALIDITY_STATE_VALID,
    EXAM_VALIDITY_TRACKING_FILTER_TRACKED,
    EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED,
    EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    EMPLOYEE_SOURCE_THP_WORKER,
    EXAM_VALIDITY_WARNING_DAYS,
    WRITTEN_RESULT_PASSED,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.repository.test_exam_validity_tracking_repository import (
    EmployeeLinkMap,
    TestExamValidityTrackingRepository,
    tracking_identities,
)
from moduly.testy.sluzby.test_definition_service import test_definition_service
from moduly.testy.sluzby.test_employee_service import test_employee_service
from moduly.testy.sluzby.test_exam_service import test_exam_service


@dataclass(frozen=True)
class ExamValidityRow:
    """Jeden řádek přehledu: zaměstnanec × test."""

    employee_id: int
    test_definition_id: int
    personal_number: str
    first_name: str
    last_name: str
    employee_name: str
    workplace_id: int | None
    workplace_name: str
    test_name: str
    test_active: bool
    employee_active: bool
    last_success_on: date | None
    valid_until: date | None
    state: str
    prepared_count: int
    in_progress_count: int
    last_success_exam_id: int | None
    tracked: bool = True
    employee_source: str = EMPLOYEE_SOURCE_TEST_EMPLOYEE


def as_local_day(value: date | None) -> date:
    """Lokální kalendářní den. Bez hodnoty vrátí dnešek."""
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("Datum pro vyhodnocení platnosti musí být date.")


def classify_successful_validity(valid_until: date | None, today: date) -> str:
    """Stav platnosti jedné úspěšné zkoušky vůči zadanému dni.

    ``valid_until`` je včetně uvedeného dne. Chybějící datum je bez omezení.
    """
    day = as_local_day(today)
    if valid_until is None:
        return EXAM_VALIDITY_STATE_UNLIMITED
    until = valid_until.date() if isinstance(valid_until, datetime) else valid_until
    remaining = (until - day).days
    if remaining > EXAM_VALIDITY_WARNING_DAYS:
        return EXAM_VALIDITY_STATE_VALID
    if remaining >= 0:
        return EXAM_VALIDITY_STATE_EXPIRING
    return EXAM_VALIDITY_STATE_EXPIRED


def exam_validity_search_text(row: ExamValidityRow) -> str:
    """Text, ve kterém hledá filtr osobního čísla, jména a názvu testu."""
    return " ".join(
        part
        for part in (
            row.personal_number,
            row.first_name,
            row.last_name,
            row.employee_name,
            row.test_name,
        )
        if part
    )


def completion_day(exam: TestExam) -> date:
    """Skutečné datum dokončení. Když chybí, zůstane datum zkoušky."""
    finished = exam.written_finished_at
    if isinstance(finished, datetime):
        return finished.date()
    if isinstance(finished, date):
        return finished
    evaluated = exam.written_evaluated_at
    if isinstance(evaluated, datetime):
        return evaluated.date()
    if isinstance(evaluated, date):
        return evaluated
    exam_day = exam.exam_date
    if isinstance(exam_day, datetime):
        return exam_day.date()
    return exam_day


def is_successful_exam(exam: TestExam) -> bool:
    return (
        exam.status == EXAM_STATUS_COMPLETED
        and exam.exam_result == WRITTEN_RESULT_PASSED
    )


def build_exam_validity_rows(
    exams: list[TestExam],
    *,
    today: date,
    employees_by_id: dict,
    tests_by_id: dict,
    workplace_names: dict[int, str],
    workers_by_id: dict | None = None,
    link_map: EmployeeLinkMap | None = None,
) -> list[ExamValidityRow]:
    """Sestaví řádky bez filtrů. Zrušená zkouška sama řádek nezaloží.

    Propojené identity se pro stejný test sejdou v jednom řádku.
    Bez řádku v mapě zůstávají i při stejném čísle oddělené.
    """
    links = link_map or EmployeeLinkMap({}, {})
    workers = workers_by_id or {}
    grouped: dict[tuple, list[TestExam]] = {}
    for exam in exams:
        if exam.status == EXAM_STATUS_CANCELLED:
            continue
        source = getattr(exam, "employee_source", None) or EMPLOYEE_SOURCE_TEST_EMPLOYEE
        person = _person_token(links, source, int(exam.employee_id))
        grouped.setdefault((person, int(exam.test_definition_id)), []).append(exam)

    day = as_local_day(today)
    rows: list[ExamValidityRow] = []
    for (person, test_id), group in grouped.items():
        source, employee_id = _display_identity(person)
        rows.append(
            _row_for_group(
                employee_id,
                test_id,
                group,
                employee_source=source,
                today=day,
                employees_by_id=employees_by_id,
                workers_by_id=workers,
                tests_by_id=tests_by_id,
                workplace_names=workplace_names,
            )
        )
    rows.sort(key=_row_sort_key)
    return rows


def _person_token(
    link_map: EmployeeLinkMap,
    employee_source: str,
    employee_id: int,
) -> tuple:
    identities = tracking_identities(link_map, employee_source, employee_id)
    if len(identities) == 2:
        by_source = dict(identities)
        return (
            "linked",
            by_source[EMPLOYEE_SOURCE_TEST_EMPLOYEE],
            by_source[EMPLOYEE_SOURCE_THP_WORKER],
        )
    return identities[0]


def _display_identity(person: tuple) -> tuple[str, int]:
    """Propojený řádek ukazuje centrálního zaměstnance."""
    if person[0] == "linked":
        return EMPLOYEE_SOURCE_THP_WORKER, int(person[2])
    return str(person[0]), int(person[1])


def validity_rows_for_summary(rows: list[ExamValidityRow]) -> list[ExamValidityRow]:
    """Řádky pro budoucí souhrn platnosti. Nesledované kombinace vynechá."""
    return [row for row in rows if row.tracked]


def unfinished_exam_counts(rows: list[ExamValidityRow]) -> tuple[int, int]:
    """Připravené a rozpracované zkoušky včetně nesledovaných kombinací."""
    return (
        sum(row.prepared_count for row in rows),
        sum(row.in_progress_count for row in rows),
    )


@dataclass(frozen=True)
class ExamRetrainingSummary:
    """Čtyři ukazatele panelu Přezkoušení zaměstnanců."""

    valid_count: int
    expiring_count: int
    expired_count: int
    unfinished_count: int


def exam_retraining_summary(rows: list[ExamValidityRow]) -> ExamRetrainingSummary:
    """Platné, končící a neplatné jen ze sledovaných kombinací.

    Nedokončené jsou jednotlivé připravené a rozpracované zkoušky,
    včetně kombinací s vypnutým sledováním. Řádky už musí odpovídat
    výběru zaměstnanců (dashboard bere jen aktivní).
    """
    tracked = validity_rows_for_summary(rows)
    prepared, in_progress = unfinished_exam_counts(rows)
    return ExamRetrainingSummary(
        valid_count=sum(row.state == EXAM_VALIDITY_STATE_VALID for row in tracked),
        expiring_count=sum(row.state == EXAM_VALIDITY_STATE_EXPIRING for row in tracked),
        expired_count=sum(row.state == EXAM_VALIDITY_STATE_EXPIRED for row in tracked),
        unfinished_count=prepared + in_progress,
    )


def filter_exam_validity_rows(
    rows: list[ExamValidityRow],
    *,
    workplace_id: int | None = None,
    test_definition_id: int | None = None,
    state: str | None = None,
    tracking: str | None = None,
    search: str = "",
) -> list[ExamValidityRow]:
    selected_workplace = None if workplace_id in (None, "") else int(workplace_id)
    selected_test = None if test_definition_id in (None, "") else int(test_definition_id)
    selected_state = str(state or "").strip() or None
    tracking_mode = str(tracking or "").strip()
    needle = " ".join(str(search or "").casefold().split())
    filtered: list[ExamValidityRow] = []
    for row in rows:
        if selected_workplace is not None and row.workplace_id != selected_workplace:
            continue
        if selected_test is not None and row.test_definition_id != selected_test:
            continue
        if selected_state is not None and row.state != selected_state:
            continue
        if tracking_mode == EXAM_VALIDITY_TRACKING_FILTER_TRACKED and not row.tracked:
            continue
        if tracking_mode == EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED and row.tracked:
            continue
        if needle:
            haystack = " ".join(exam_validity_search_text(row).casefold().split())
            if needle not in haystack:
                continue
        filtered.append(row)
    return filtered


class ExamValidityService:
    def __init__(self) -> None:
        self.tracking = TestExamValidityTrackingRepository()

    def stop_tracking(
        self,
        employee_id: int,
        test_definition_id: int,
        *,
        employee_source: str = EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    ) -> None:
        """Vypne sledování. Zkoušky ani jejich údaje nemění.

        U propojené osoby zapíše značku pro obě identity.
        """
        self.tracking.stop(
            employee_id,
            test_definition_id,
            employee_source=employee_source,
        )

    def resume_tracking(
        self,
        employee_id: int,
        test_definition_id: int,
        *,
        employee_source: str = EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    ) -> None:
        """Ručně obnoví sledování bez založení nové zkoušky."""
        self.tracking.resume(
            employee_id,
            test_definition_id,
            employee_source=employee_source,
        )

    def retraining_summary(self, *, today: date | None = None) -> ExamRetrainingSummary:
        """Souhrn pro dashboard. Stejná platnost jako přehled, jen aktivní zaměstnanci."""
        rows = self.list_rows(today=today, include_inactive_employees=False)
        return exam_retraining_summary(rows)

    def list_rows(
        self,
        *,
        today: date | None = None,
        include_inactive_employees: bool = False,
    ) -> list[ExamValidityRow]:
        """Všechny evidované kombinace. Další filtry řeší ``filter_exam_validity_rows``."""
        day = as_local_day(today)
        employees = {
            int(employee.id): employee
            for employee in test_employee_service.list_employees(include_inactive=True)
        }
        tests = {
            int(test.id): test
            for test in test_definition_service.list_tests(include_inactive=True)
        }
        workplace_names = {
            int(workplace.id): workplace.name
            for workplace in settings_service.get_workplaces(include_inactive=True)
        }
        workers = {
            int(worker.id): worker
            for worker in settings_service.get_workers(include_inactive=True)
        }
        link_map = self.tracking.link_map()
        rows = build_exam_validity_rows(
            test_exam_service.list_exams(),
            today=day,
            employees_by_id=employees,
            tests_by_id=tests,
            workplace_names=workplace_names,
            workers_by_id=workers,
            link_map=link_map,
        )
        untracked = self.tracking.untracked_pairs()
        if untracked:
            rows = [
                replace(row, tracked=False)
                if _row_is_untracked(row, link_map, untracked)
                else row
                for row in rows
            ]
        if include_inactive_employees:
            return rows
        return [row for row in rows if row.employee_active]


def _row_is_untracked(
    row: ExamValidityRow,
    link_map: EmployeeLinkMap,
    untracked: set[tuple[str, int, int]],
) -> bool:
    """Stačí značka u jedné z propojených identit."""
    return any(
        (source, person_id, row.test_definition_id) in untracked
        for source, person_id in tracking_identities(
            link_map,
            row.employee_source,
            row.employee_id,
        )
    )


def _row_for_group(
    employee_id: int,
    test_id: int,
    group: list[TestExam],
    *,
    employee_source: str,
    today: date,
    employees_by_id: dict,
    workers_by_id: dict,
    tests_by_id: dict,
    workplace_names: dict[int, str],
) -> ExamValidityRow:
    prepared_count = sum(1 for exam in group if exam.status == EXAM_STATUS_PREPARED)
    in_progress_count = sum(1 for exam in group if exam.status == EXAM_STATUS_STARTED)
    successful = [exam for exam in group if is_successful_exam(exam)]
    if successful:
        chosen = max(successful, key=lambda exam: (completion_day(exam), int(exam.id or 0)))
        valid_until = chosen.valid_until
        if isinstance(valid_until, datetime):
            valid_until = valid_until.date()
        state = classify_successful_validity(valid_until, today)
        last_success_on = completion_day(chosen)
        last_success_exam_id = int(chosen.id)
    else:
        valid_until = None
        state = EXAM_VALIDITY_STATE_NO_SUCCESS
        last_success_on = None
        last_success_exam_id = None

    test = tests_by_id.get(test_id)
    snapshot = max(group, key=lambda exam: int(exam.id or 0))
    if employee_source == EMPLOYEE_SOURCE_THP_WORKER:
        person = workers_by_id.get(employee_id)
    else:
        person = employees_by_id.get(employee_id)
    if person is not None:
        workplace_id = int(person.workplace_id) if person.workplace_id else None
        personal_number = person.personal_number or ""
        first_name = person.first_name
        last_name = person.last_name
        employee_name = person.display_name
        employee_active = bool(person.active)
        workplace_name = workplace_names.get(workplace_id or -1, "")
    else:
        workplace_id = None
        personal_number = snapshot.employee_personal_number
        first_name = snapshot.employee_first_name
        last_name = snapshot.employee_last_name
        employee_name = snapshot.employee_display_name
        employee_active = False
        workplace_name = snapshot.employee_workplace_name or ""
    if test is not None:
        test_name = test.name
        test_active = bool(test.active)
    else:
        test_name = snapshot.test_name
        test_active = True
    return ExamValidityRow(
        employee_id=employee_id,
        test_definition_id=test_id,
        personal_number=personal_number,
        first_name=first_name,
        last_name=last_name,
        employee_name=employee_name,
        workplace_id=workplace_id,
        workplace_name=workplace_name,
        test_name=test_name,
        test_active=test_active,
        employee_active=employee_active,
        last_success_on=last_success_on,
        valid_until=valid_until,
        state=state,
        prepared_count=prepared_count,
        in_progress_count=in_progress_count,
        last_success_exam_id=last_success_exam_id,
        employee_source=employee_source,
    )


def _row_sort_key(row: ExamValidityRow) -> tuple:
    return (
        czech_sort_key(row.last_name),
        czech_sort_key(row.first_name),
        czech_sort_key(row.personal_number),
        czech_sort_key(row.test_name),
        row.employee_source,
        row.employee_id,
        row.test_definition_id,
    )


exam_validity_service = ExamValidityService()
