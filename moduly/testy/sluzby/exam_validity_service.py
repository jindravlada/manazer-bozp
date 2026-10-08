"""Evidenční přehled platnosti skutečně založených zkoušek.

Nevytváří povinné testy ani nemění uložený výsledek zkoušky.
Platnost se odvozuje z poslední úspěšně dokončené zkoušky dané
kombinace zaměstnanec × test.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    EXAM_VALIDITY_WARNING_DAYS,
    WRITTEN_RESULT_PASSED,
)
from moduly.testy.modely.test_exam import TestExam
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
) -> list[ExamValidityRow]:
    """Sestaví řádky bez filtrů. Zrušená zkouška sama řádek nezaloží."""
    grouped: dict[tuple[int, int], list[TestExam]] = {}
    for exam in exams:
        if exam.status == EXAM_STATUS_CANCELLED:
            continue
        key = (int(exam.employee_id), int(exam.test_definition_id))
        grouped.setdefault(key, []).append(exam)

    day = as_local_day(today)
    rows: list[ExamValidityRow] = []
    for (employee_id, test_id), group in grouped.items():
        rows.append(
            _row_for_group(
                employee_id,
                test_id,
                group,
                today=day,
                employees_by_id=employees_by_id,
                tests_by_id=tests_by_id,
                workplace_names=workplace_names,
            )
        )
    rows.sort(key=_row_sort_key)
    return rows


def filter_exam_validity_rows(
    rows: list[ExamValidityRow],
    *,
    workplace_id: int | None = None,
    test_definition_id: int | None = None,
    state: str | None = None,
    search: str = "",
) -> list[ExamValidityRow]:
    selected_workplace = None if workplace_id in (None, "") else int(workplace_id)
    selected_test = None if test_definition_id in (None, "") else int(test_definition_id)
    selected_state = str(state or "").strip() or None
    needle = " ".join(str(search or "").casefold().split())
    filtered: list[ExamValidityRow] = []
    for row in rows:
        if selected_workplace is not None and row.workplace_id != selected_workplace:
            continue
        if selected_test is not None and row.test_definition_id != selected_test:
            continue
        if selected_state is not None and row.state != selected_state:
            continue
        if needle:
            haystack = " ".join(exam_validity_search_text(row).casefold().split())
            if needle not in haystack:
                continue
        filtered.append(row)
    return filtered


class ExamValidityService:
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
        rows = build_exam_validity_rows(
            test_exam_service.list_exams(),
            today=day,
            employees_by_id=employees,
            tests_by_id=tests,
            workplace_names=workplace_names,
        )
        if include_inactive_employees:
            return rows
        return [row for row in rows if row.employee_active]


def _row_for_group(
    employee_id: int,
    test_id: int,
    group: list[TestExam],
    *,
    today: date,
    employees_by_id: dict,
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

    employee = employees_by_id.get(employee_id)
    test = tests_by_id.get(test_id)
    snapshot = max(group, key=lambda exam: int(exam.id or 0))
    if employee is not None:
        workplace_id = int(employee.workplace_id) if employee.workplace_id else None
        personal_number = employee.personal_number
        first_name = employee.first_name
        last_name = employee.last_name
        employee_name = employee.display_name
        employee_active = bool(employee.active)
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
    )


def _row_sort_key(row: ExamValidityRow) -> tuple:
    return (
        czech_sort_key(row.last_name),
        czech_sort_key(row.first_name),
        czech_sort_key(row.personal_number),
        czech_sort_key(row.test_name),
        row.employee_id,
        row.test_definition_id,
    )


exam_validity_service = ExamValidityService()
