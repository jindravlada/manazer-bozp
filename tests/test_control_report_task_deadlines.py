"""CONTROL-REPORT-TASK-DEADLINES-8: helper souhrnu navazujících úkolů."""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from core.shared.sluzby.control_report_task_deadlines import (
    ALL_TASKS_TERMINAL_SENTENCE,
    NO_LINKED_TASKS_SENTENCE,
    format_linked_tasks_assessment_sentence,
    format_linked_tasks_overview_lines,
    format_report_date,
    summarize_linked_task_deadlines,
)
from moduly.ukoly.constants import (
    TASK_STATUS_ACTIVE,
    TASK_STATUS_CANCELED,
    TASK_STATUS_CLOSED,
    TASK_STATUS_WAITING_CHECK,
)
from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date


def _finding(finding_id: int, task_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(id=finding_id, task_id=task_id)


def _task(
    task_id: int,
    *,
    status: str,
    due_date: date | None = None,
    check_due_date: date | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=task_id,
        computed_status=status,
        due_date=due_date,
        check_due_date=check_due_date,
    )


class ControlReportTaskDeadlinesHelperTestCase(unittest.TestCase):
    def test_no_findings_no_tasks_no_assessment_sentence(self) -> None:
        summary = summarize_linked_task_deadlines([], {}, log_missing=False)
        self.assertEqual("", format_linked_tasks_assessment_sentence(summary))
        self.assertEqual(
            ["Otevřené úkoly: 0"],
            format_linked_tasks_overview_lines(summary),
        )

    def test_findings_without_tasks(self) -> None:
        findings = [_finding(1, None), _finding(2, None)]
        summary = summarize_linked_task_deadlines(findings, {}, log_missing=False)
        self.assertEqual(2, summary.finding_count)
        self.assertEqual(0, summary.linked_task_count)
        self.assertEqual(
            NO_LINKED_TASKS_SENTENCE,
            format_linked_tasks_assessment_sentence(summary),
        )
        self.assertEqual(
            ["Otevřené úkoly: 0"],
            format_linked_tasks_overview_lines(summary),
        )

    def test_one_open_task_with_due(self) -> None:
        due = date(2026, 10, 31)
        task = _task(10, status=TASK_STATUS_ACTIVE, due_date=due)
        summary = summarize_linked_task_deadlines(
            [_finding(1, 10)],
            {10: task},
            log_missing=False,
        )
        self.assertEqual(1, summary.open_count)
        self.assertEqual(due, summary.latest_due_date)
        self.assertEqual(
            "Evidence obsahuje 1 otevřený navazující úkol. "
            "Nejzazší evidovaný termín otevřených úkolů je 31. 10. 2026.",
            format_linked_tasks_assessment_sentence(summary),
        )
        self.assertEqual(
            [
                "Otevřené úkoly: 1",
                "Nejzazší evidovaný termín: 31. 10. 2026",
            ],
            format_linked_tasks_overview_lines(summary),
        )

    def test_few_and_many_open_forms(self) -> None:
        few = [
            _task(i, status=TASK_STATUS_ACTIVE, due_date=date(2026, 10, i))
            for i in range(1, 4)
        ]
        few_map = {task.id: task for task in few}
        few_findings = [_finding(i, task.id) for i, task in enumerate(few, start=1)]
        few_summary = summarize_linked_task_deadlines(
            few_findings, few_map, log_missing=False
        )
        self.assertIn(
            "3 otevřené navazující úkoly",
            format_linked_tasks_assessment_sentence(few_summary),
        )

        many = [
            _task(i, status=TASK_STATUS_ACTIVE, due_date=date(2026, 11, i))
            for i in range(1, 6)
        ]
        many_map = {task.id: task for task in many}
        many_findings = [_finding(i, task.id) for i, task in enumerate(many, start=1)]
        many_summary = summarize_linked_task_deadlines(
            many_findings, many_map, log_missing=False
        )
        self.assertIn(
            "5 otevřených navazujících úkolů",
            format_linked_tasks_assessment_sentence(many_summary),
        )
        self.assertEqual(date(2026, 11, 5), many_summary.latest_due_date)

    def test_some_open_without_due_hides_latest(self) -> None:
        tasks = {
            1: _task(1, status=TASK_STATUS_ACTIVE, due_date=date(2026, 10, 31)),
            2: _task(2, status=TASK_STATUS_ACTIVE, due_date=None),
        }
        findings = [_finding(1, 1), _finding(2, 2), _finding(3, 1)]
        summary = summarize_linked_task_deadlines(
            findings, tasks, log_missing=False
        )
        self.assertEqual(2, summary.open_count)
        self.assertEqual(1, summary.open_without_due_count)
        self.assertIsNone(summary.latest_due_date)
        self.assertEqual(
            "Evidence obsahuje 2 otevřené navazující úkoly; "
            "1 z nich nemá stanovený termín.",
            format_linked_tasks_assessment_sentence(summary),
        )
        self.assertEqual(
            [
                "Otevřené úkoly: 2",
                "Otevřené úkoly bez termínu: 1",
            ],
            format_linked_tasks_overview_lines(summary),
        )
        self.assertNotIn("Nejzazší evidovaný termín", "\n".join(
            format_linked_tasks_overview_lines(summary)
        ))

    def test_all_terminal(self) -> None:
        tasks = {
            1: _task(1, status=TASK_STATUS_CLOSED, due_date=date(2026, 1, 1)),
            2: _task(2, status=TASK_STATUS_CANCELED, due_date=date(2026, 1, 2)),
        }
        findings = [_finding(1, 1), _finding(2, 2)]
        summary = summarize_linked_task_deadlines(
            findings, tasks, log_missing=False
        )
        self.assertEqual(0, summary.open_count)
        self.assertEqual(2, summary.terminal_count)
        self.assertEqual(
            ALL_TASKS_TERMINAL_SENTENCE,
            format_linked_tasks_assessment_sentence(summary),
        )
        self.assertEqual(
            ["Otevřené úkoly: 0"],
            format_linked_tasks_overview_lines(summary),
        )

    def test_mix_active_closed_canceled(self) -> None:
        tasks = {
            1: _task(1, status=TASK_STATUS_ACTIVE, due_date=date(2026, 10, 31)),
            2: _task(2, status=TASK_STATUS_CLOSED, due_date=date(2026, 9, 1)),
            3: _task(3, status=TASK_STATUS_CANCELED, due_date=date(2026, 8, 1)),
        }
        findings = [_finding(1, 1), _finding(2, 2), _finding(3, 3)]
        summary = summarize_linked_task_deadlines(
            findings, tasks, log_missing=False
        )
        self.assertEqual(1, summary.open_count)
        self.assertEqual(2, summary.terminal_count)
        self.assertEqual(0, summary.missing_task_link_count)
        self.assertEqual(3, summary.linked_task_count)

    def test_waiting_check_uses_check_due_date_not_due_date(self) -> None:
        old_due = date(2026, 5, 1)
        check_due = date(2026, 11, 15)
        task = _task(
            1,
            status=TASK_STATUS_WAITING_CHECK,
            due_date=old_due,
            check_due_date=check_due,
        )
        self.assertEqual(check_due, task_urgency_due_date(task))
        summary = summarize_linked_task_deadlines(
            [_finding(1, 1)],
            {1: task},
            log_missing=False,
        )
        self.assertEqual(check_due, summary.latest_due_date)
        self.assertIn("15. 11. 2026", format_linked_tasks_assessment_sentence(summary))

    def test_waiting_check_without_check_due_is_without_due(self) -> None:
        task = _task(
            1,
            status=TASK_STATUS_WAITING_CHECK,
            due_date=date(2026, 5, 1),
            check_due_date=None,
        )
        self.assertIsNone(task_urgency_due_date(task))
        summary = summarize_linked_task_deadlines(
            [_finding(1, 1)],
            {1: task},
            log_missing=False,
        )
        self.assertEqual(1, summary.open_without_due_count)
        self.assertIsNone(summary.latest_due_date)
        self.assertIn("nemá stanovený termín", format_linked_tasks_assessment_sentence(summary))

    def test_missing_link_logged_and_not_counted(self) -> None:
        findings = [_finding(7, 99)]
        with self.assertLogs(
            "core.shared.sluzby.control_report_task_deadlines",
            level="WARNING",
        ) as logged:
            summary = summarize_linked_task_deadlines(findings, {})
        self.assertEqual(1, summary.missing_task_link_count)
        self.assertEqual(0, summary.linked_task_count)
        self.assertEqual(0, summary.open_count)
        self.assertEqual(NO_LINKED_TASKS_SENTENCE, format_linked_tasks_assessment_sentence(summary))
        self.assertTrue(any("7" in line and "99" in line for line in logged.output))
        sentence = format_linked_tasks_assessment_sentence(summary)
        self.assertNotIn("99", sentence)
        self.assertNotIn("Finding 7", sentence)

    def test_report_date_format(self) -> None:
        self.assertEqual("31. 10. 2026", format_report_date(date(2026, 10, 31)))
        self.assertEqual("05. 03. 2026", format_report_date(date(2026, 3, 5)))


if __name__ == "__main__":
    unittest.main()
