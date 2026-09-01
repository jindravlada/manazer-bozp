"""STATE-SUPERVISION-ATTENTION-6A1: červená kostička za prošlé lhůty a problémy."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()
_NOW = datetime(2026, 6, 15, 12, 0, 0)
_TODAY = _NOW.date()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.theme.status_colors import STATUS_DONE_BG, STATUS_MISSING_BG, STATUS_NEUTRAL_BG
    from core.widgets.editor_dialog_controller import EditorDialogController
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ATTENTION_EVALUATION_FAILED_MESSAGE,
        ATTENTION_REASON_MISSING_TASKS,
        ATTENTION_REASON_OVERDUE_DOCUMENTS,
        ATTENTION_REASON_OVERDUE_FINDINGS,
        ATTENTION_REASON_OVERDUE_OBJECTIONS,
        ATTENTION_REASON_OVERDUE_PLANNED_START,
        ATTENTION_REASON_OVERDUE_TASKS,
        ATTENTION_TOOLTIP_ALERT_HEADING,
        ATTENTION_TOOLTIP_STATUS_PREFIX,
        COL_STATUS,
        FILTER_MODE_CLOSED,
        STATUS_ANNOUNCED,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_CUBE_HINT,
        STATUS_MEASURES_IN_PROGRESS,
        STATUS_PREPARATION,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
        TAB_ANNOUNCEMENT,
    )
    from moduly.statni_dozor.sluzby.state_supervision_attention import (
        attention_for_supervision,
        state_supervision_attention_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab
    from moduly.statni_dozor.ui.state_supervision_table import (
        STATUS_CUBE_ALERT_COLOR,
        STATUS_CUBE_COLORS,
        status_cube_color,
        status_cube_tooltip,
    )
    from moduly.ukoly.constants import (
        TASK_STATUS_ACTIVE,
        TASK_STATUS_CANCELED,
        TASK_STATUS_CLOSED,
        TASK_STATUS_WAITING_CHECK,
    )
    from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date
    from moduly.ukoly.sluzby.task_service import task_service


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _record(**fields) -> SimpleNamespace:
    payload = {"id": 1, "status": STATUS_ANNOUNCED}
    payload.update(fields)
    return SimpleNamespace(**payload)


def _doc(**fields) -> SimpleNamespace:
    payload = {
        "active": True,
        "due_at": None,
        "prepared_at": None,
        "submitted_at": None,
        "state_supervision_id": 1,
    }
    payload.update(fields)
    return SimpleNamespace(**payload)


def _finding(**fields) -> SimpleNamespace:
    payload = {
        "status": FINDING_STATUS_OTEVRENE,
        "due_date": None,
        "task_id": None,
        "entity_id": 1,
    }
    payload.update(fields)
    return SimpleNamespace(**payload)


def _task(task_id: int, *, computed_status: str, due_date=None, check_due_date=None):
    return SimpleNamespace(
        id=task_id,
        computed_status=computed_status,
        due_date=due_date,
        check_due_date=check_due_date,
    )


class StateSupervisionAttention6a1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        cls._app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _supervision(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _open_tab(self) -> StateSupervisionTab:
        return StateSupervisionTab()

    def _status_item(self, tab: StateSupervisionTab, supervision_id: int):
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, COL_STATUS)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == supervision_id:
                return item
        self.fail(f"řádek {supervision_id} v přehledu chybí")

    def test_01_documents_overdue_rules(self) -> None:
        past = _NOW - timedelta(minutes=1)
        future = _NOW + timedelta(minutes=1)
        overdue = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=past)],
            now=_NOW,
        )
        self.assertEqual(overdue.overdue_documents_count, 1)
        self.assertTrue(overdue.has_alert)
        self.assertEqual(overdue.reasons[0].code, ATTENTION_REASON_OVERDUE_DOCUMENTS)

        prepared = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=past, prepared_at=past)],
            now=_NOW,
        )
        self.assertEqual(prepared.overdue_documents_count, 1)

        submitted = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=past, submitted_at=past)],
            now=_NOW,
        )
        self.assertEqual(submitted.overdue_documents_count, 0)
        self.assertFalse(submitted.has_alert)

        inactive = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=past, active=False)],
            now=_NOW,
        )
        self.assertEqual(inactive.overdue_documents_count, 0)

        no_due = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=None)],
            now=_NOW,
        )
        self.assertEqual(no_due.overdue_documents_count, 0)

        equal = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=_NOW)],
            now=_NOW,
        )
        self.assertEqual(equal.overdue_documents_count, 0)
        future_row = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=future)],
            now=_NOW,
        )
        self.assertEqual(future_row.overdue_documents_count, 0)

    def test_02_findings_overdue_rules(self) -> None:
        yesterday = _TODAY - timedelta(days=1)
        open_overdue = attention_for_supervision(
            _record(),
            findings=[_finding(status=FINDING_STATUS_OTEVRENE, due_date=yesterday)],
            now=_NOW,
        )
        self.assertEqual(open_overdue.overdue_findings_count, 1)

        progress = attention_for_supervision(
            _record(),
            findings=[_finding(status=FINDING_STATUS_V_PROCESU, due_date=yesterday)],
            now=_NOW,
        )
        self.assertEqual(progress.overdue_findings_count, 1)

        resolved = attention_for_supervision(
            _record(),
            findings=[_finding(status=FINDING_STATUS_VYPORADANO, due_date=yesterday)],
            now=_NOW,
        )
        self.assertEqual(resolved.overdue_findings_count, 0)

        today_due = attention_for_supervision(
            _record(),
            findings=[_finding(due_date=_TODAY)],
            now=_NOW,
        )
        self.assertEqual(today_due.overdue_findings_count, 0)

        no_due = attention_for_supervision(
            _record(),
            findings=[_finding(due_date=None)],
            now=_NOW,
        )
        self.assertEqual(no_due.overdue_findings_count, 0)

    def test_03_tasks_urgency_and_missing(self) -> None:
        yesterday = _TODAY - timedelta(days=1)
        tomorrow = _TODAY + timedelta(days=1)
        active_overdue = _task(
            1, computed_status=TASK_STATUS_ACTIVE, due_date=yesterday
        )
        self.assertEqual(task_urgency_due_date(active_overdue), yesterday)
        result = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=1)],
            tasks_by_id={1: active_overdue},
            now=_NOW,
        )
        self.assertEqual(result.overdue_tasks_count, 1)

        active_ok = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=2)],
            tasks_by_id={
                2: _task(2, computed_status=TASK_STATUS_ACTIVE, due_date=tomorrow)
            },
            now=_NOW,
        )
        self.assertEqual(active_ok.overdue_tasks_count, 0)

        waiting_ok = _task(
            3,
            computed_status=TASK_STATUS_WAITING_CHECK,
            due_date=yesterday,
            check_due_date=tomorrow,
        )
        self.assertEqual(task_urgency_due_date(waiting_ok), tomorrow)
        waiting = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=3)],
            tasks_by_id={3: waiting_ok},
            now=_NOW,
        )
        self.assertEqual(waiting.overdue_tasks_count, 0)

        waiting_late = _task(
            4,
            computed_status=TASK_STATUS_WAITING_CHECK,
            due_date=tomorrow,
            check_due_date=yesterday,
        )
        late = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=4)],
            tasks_by_id={4: waiting_late},
            now=_NOW,
        )
        self.assertEqual(late.overdue_tasks_count, 1)

        closed = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=5)],
            tasks_by_id={
                5: _task(5, computed_status=TASK_STATUS_CLOSED, due_date=yesterday)
            },
            now=_NOW,
        )
        self.assertEqual(closed.overdue_tasks_count, 0)

        canceled = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=6)],
            tasks_by_id={
                6: _task(6, computed_status=TASK_STATUS_CANCELED, due_date=yesterday)
            },
            now=_NOW,
        )
        self.assertEqual(canceled.overdue_tasks_count, 0)

        no_due = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=7)],
            tasks_by_id={7: _task(7, computed_status=TASK_STATUS_ACTIVE)},
            now=_NOW,
        )
        self.assertEqual(no_due.overdue_tasks_count, 0)

        missing = attention_for_supervision(
            _record(),
            findings=[_finding(task_id=99)],
            tasks_by_id={},
            now=_NOW,
        )
        self.assertEqual(missing.missing_tasks_count, 1)
        self.assertEqual(missing.overdue_tasks_count, 0)
        self.assertTrue(missing.has_alert)
        self.assertEqual(missing.reasons[0].code, ATTENTION_REASON_MISSING_TASKS)

    def test_04_objections_and_planned_start(self) -> None:
        past = _NOW - timedelta(hours=1)
        future = _NOW + timedelta(hours=1)
        overdue = attention_for_supervision(
            _record(objections_due_at=past),
            now=_NOW,
        )
        self.assertTrue(overdue.overdue_objections)
        self.assertEqual(overdue.reasons[0].code, ATTENTION_REASON_OVERDUE_OBJECTIONS)

        submitted = attention_for_supervision(
            _record(objections_due_at=past, objections_submitted_at=past),
            now=_NOW,
        )
        self.assertFalse(submitted.overdue_objections)

        upcoming = attention_for_supervision(
            _record(objections_due_at=future),
            now=_NOW,
        )
        self.assertFalse(upcoming.overdue_objections)

        equal = attention_for_supervision(
            _record(objections_due_at=_NOW),
            now=_NOW,
        )
        self.assertFalse(equal.overdue_objections)

        planned = attention_for_supervision(
            _record(planned_start_at=past),
            now=_NOW,
        )
        self.assertTrue(planned.overdue_planned_start)
        self.assertEqual(planned.reasons[0].code, ATTENTION_REASON_OVERDUE_PLANNED_START)

        started = attention_for_supervision(
            _record(planned_start_at=past, started_at=past),
            now=_NOW,
        )
        self.assertFalse(started.overdue_planned_start)

        closed = attention_for_supervision(
            _record(status=STATUS_CLOSED, planned_start_at=past),
            now=_NOW,
        )
        self.assertFalse(closed.overdue_planned_start)

        cancelled = attention_for_supervision(
            _record(status=STATUS_CANCELLED, planned_start_at=past),
            now=_NOW,
        )
        self.assertFalse(cancelled.overdue_planned_start)
        self.assertFalse(cancelled.has_alert)

        planned_equal = attention_for_supervision(
            _record(planned_start_at=_NOW),
            now=_NOW,
        )
        self.assertFalse(planned_equal.overdue_planned_start)

    def test_05_colors_tooltip_and_hint(self) -> None:
        none = attention_for_supervision(_record(), now=_NOW)
        self.assertEqual(
            status_cube_color(STATUS_MEASURES_IN_PROGRESS, none),
            STATUS_CUBE_COLORS[STATUS_MEASURES_IN_PROGRESS],
        )
        self.assertEqual(status_cube_color(STATUS_CLOSED, none), STATUS_DONE_BG)
        alert = attention_for_supervision(
            _record(),
            documents=[_doc(due_at=_NOW - timedelta(days=1))],
            now=_NOW,
        )
        self.assertEqual(
            status_cube_color(STATUS_PREPARATION, alert),
            STATUS_CUBE_ALERT_COLOR,
        )
        self.assertEqual(STATUS_CUBE_ALERT_COLOR, STATUS_MISSING_BG)
        self.assertEqual(status_cube_color(STATUS_CLOSED, alert), STATUS_CUBE_ALERT_COLOR)
        self.assertEqual(
            status_cube_color(STATUS_CANCELLED, alert),
            STATUS_NEUTRAL_BG,
        )
        self.assertEqual(
            status_cube_color(STATUS_CLOSED, none, evaluation_failed=True),
            STATUS_NEUTRAL_BG,
        )

        clean_tip = status_cube_tooltip(STATUS_MEASURES_IN_PROGRESS, none)
        self.assertIn(f"{ATTENTION_TOOLTIP_STATUS_PREFIX} Plnění opatření.", clean_tip)
        self.assertNotIn(ATTENTION_TOOLTIP_ALERT_HEADING, clean_tip)
        self.assertNotIn("Po termínu", clean_tip.replace("po termínu", ""))

        mixed = attention_for_supervision(
            _record(objections_due_at=_NOW - timedelta(days=1)),
            documents=[_doc(due_at=_NOW - timedelta(days=1))],
            findings=[
                _finding(due_date=_TODAY - timedelta(days=1)),
                _finding(task_id=9),
            ],
            now=_NOW,
        )
        tip = status_cube_tooltip(STATUS_MEASURES_IN_PROGRESS, mixed)
        self.assertIn(f"{ATTENTION_TOOLTIP_STATUS_PREFIX} Plnění opatření.", tip)
        self.assertIn(ATTENTION_TOOLTIP_ALERT_HEADING, tip)
        self.assertIn("požadované doklady po termínu: 1", tip)
        self.assertIn("zjištění po termínu: 1", tip)
        self.assertIn("chybějící navázané úkoly: 1", tip)
        self.assertIn("uplynula lhůta pro podání námitek", tip)
        self.assertNotIn("navazující úkoly po termínu", tip)
        cancelled_tip = status_cube_tooltip(STATUS_CANCELLED, mixed)
        self.assertIn("Zrušena", cancelled_tip)
        self.assertNotIn(ATTENTION_TOOLTIP_ALERT_HEADING, cancelled_tip)

        tab = self._open_tab()
        self.assertEqual(tab.hint_label.text(), STATUS_CUBE_HINT)
        self.assertIn("Červená upozorňuje", tab.hint_label.text())
        self.assertIn("color: #666", tab.hint_label.styleSheet())
        tab.close()

    def test_06_batch_load_no_n_plus_one_and_no_write(self) -> None:
        first = self._supervision()
        second = self._supervision(authority_name=f"KHS {self.marker}")
        past = datetime(2020, 1, 1, 8, 0, 0)
        state_supervision_required_document_service.create_document(
            first.id, title="Protokol", due_at=past
        )
        task = task_service.create_task(
            title=f"Opatření {self.marker}",
            due_date=date(2020, 1, 1),
            requires_verification=False,
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            first.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Otevřené",
            due_date=date(2020, 1, 1),
            task_id=task.id,
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            second.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Chybějící",
            task_id=7_001_001,
        )
        before_docs = _count("state_supervision_required_documents")
        before_findings = _count("findings")
        before_tasks = _count("tasks")
        doc_calls: list[list[int]] = []
        finding_calls: list[list[int]] = []
        task_calls: list[list[int]] = []

        def load_docs(ids):
            doc_calls.append(list(ids))
            return state_supervision_required_document_service.list_for_supervisions(ids)

        def load_findings(ids):
            finding_calls.append(list(ids))
            return finding_service.get_for_entities(ENTITY_STATE_SUPERVISION, list(ids))

        def load_tasks(ids):
            task_calls.append(list(ids))
            return task_service.get_tasks_by_ids(list(ids))

        with (
            patch.object(Session, "commit") as commit,
            patch.object(Session, "flush") as flush,
        ):
            summary = state_supervision_attention_service.summarize(
                [first, second],
                now=_NOW,
                load_documents=load_docs,
                load_findings=load_findings,
                load_tasks=load_tasks,
            )
            commit.assert_not_called()
            flush.assert_not_called()
        self.assertEqual(len(doc_calls), 1)
        self.assertEqual(len(finding_calls), 1)
        self.assertEqual(len(task_calls), 1)
        self.assertEqual(summary[first.id].overdue_documents_count, 1)
        self.assertEqual(summary[first.id].overdue_findings_count, 1)
        self.assertEqual(summary[first.id].overdue_tasks_count, 1)
        self.assertEqual(summary[second.id].missing_tasks_count, 1)
        self.assertEqual(_count("state_supervision_required_documents"), before_docs)
        self.assertEqual(_count("findings"), before_findings)
        self.assertEqual(_count("tasks"), before_tasks)

    def test_07_overview_colors_filters_and_sort(self) -> None:
        past = datetime(2020, 2, 1, 8, 0, 0)
        clean = self._supervision(
            status=STATUS_PREPARATION,
            authority_name=f"Čistá {self.marker}",
            started_at=datetime(2026, 5, 1, 8, 0, 0),
        )
        closed_alert = self._supervision(
            status=STATUS_CLOSED,
            closed_at=datetime(2026, 5, 2, 12, 0, 0),
            authority_name=f"Uzavřená {self.marker}",
            started_at=datetime(2026, 4, 1, 8, 0, 0),
        )
        state_supervision_required_document_service.create_document(
            closed_alert.id, title="Doklad po termínu", due_at=past
        )
        cancelled = self._supervision(
            status=STATUS_CANCELLED,
            authority_name=f"Zrušená {self.marker}",
            planned_start_at=past,
        )
        announced_alert = self._supervision(
            authority_name=f"Ohlášená {self.marker}",
            planned_start_at=past,
        )
        tab = self._open_tab()
        tab.text_filter.search_edit.setText(self.marker)
        clean_item = self._status_item(tab, clean.id)
        closed_item = self._status_item(tab, closed_alert.id)
        cancelled_item = self._status_item(tab, cancelled.id)
        announced_item = self._status_item(tab, announced_alert.id)
        self.assertEqual(clean_item.background().color(), QColor(STATUS_CUBE_COLORS[STATUS_PREPARATION]))
        self.assertEqual(closed_item.background().color(), QColor(STATUS_CUBE_ALERT_COLOR))
        self.assertEqual(cancelled_item.background().color(), QColor(STATUS_NEUTRAL_BG))
        self.assertEqual(announced_item.background().color(), QColor(STATUS_CUBE_ALERT_COLOR))
        self.assertIn(ATTENTION_TOOLTIP_ALERT_HEADING, closed_item.toolTip())
        self.assertIn("Uzavřena", closed_item.toolTip())
        self.assertNotIn(ATTENTION_TOOLTIP_ALERT_HEADING, cancelled_item.toolTip())

        tab.mode_filter.setCurrentText(FILTER_MODE_CLOSED)
        visible = {
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        }
        self.assertEqual(visible, {closed_alert.id})
        tab.mode_filter.setCurrentIndex(0)
        tab.status_filter.setCurrentIndex(
            tab.status_filter.findData(STATUS_CANCELLED)
        )
        visible = {
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        }
        self.assertEqual(visible, {cancelled.id})
        tab.status_filter.setCurrentIndex(0)
        tab.table.sortItems(COL_STATUS, Qt.SortOrder.AscendingOrder)
        ordered = [
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        ]
        alert_ids = {closed_alert.id, announced_alert.id}
        self.assertTrue(set(ordered[:2]) == alert_ids)
        self.assertIn(clean.id, ordered[2:])
        tab.close()

        later = self._supervision(
            authority_name=f"Novější {self.marker}",
            started_at=datetime(2026, 8, 1, 8, 0, 0),
        )
        earlier = self._supervision(
            authority_name=f"Starší {self.marker}",
            started_at=datetime(2026, 3, 1, 8, 0, 0),
        )
        fresh = self._open_tab()
        fresh.text_filter.search_edit.setText(self.marker)
        date_order = [
            fresh.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(fresh.table.rowCount())
            if not fresh.table.isRowHidden(row)
        ]
        self.assertLess(date_order.index(later.id), date_order.index(earlier.id))
        self.assertEqual(fresh.table.horizontalHeader().sortIndicatorSection(), -1)
        fresh.close()

    def test_08_attention_error_keeps_overview_neutral(self) -> None:
        closed = self._supervision(
            status=STATUS_CLOSED,
            closed_at=datetime(2026, 5, 1, 12, 0, 0),
            authority_name=f"Chyba {self.marker}",
        )
        before = _count("state_supervisions")
        with patch.object(
            state_supervision_attention_service,
            "summarize",
            side_effect=RuntimeError("boom"),
        ):
            tab = self._open_tab()
        tab.text_filter.search_edit.setText(self.marker)
        item = self._status_item(tab, closed.id)
        self.assertEqual(item.background().color(), QColor(STATUS_NEUTRAL_BG))
        self.assertNotEqual(item.background().color(), QColor(STATUS_DONE_BG))
        self.assertIn(ATTENTION_EVALUATION_FAILED_MESSAGE, item.toolTip())
        self.assertIn("Uzavřena", item.toolTip())
        self.assertEqual(_count("state_supervisions"), before)
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        page.close()
        tab.close()

    def test_09_editor_tabs_and_bundle_untouched(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.tabs.count(), 5)
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        self.assertIsInstance(dialog._editor, EditorDialogController)
        dialog.close()
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        self.assertIn("save_supervision_bundle", persist)
        self.assertNotIn("state_supervision_attention", persist)


if __name__ == "__main__":
    unittest.main()
