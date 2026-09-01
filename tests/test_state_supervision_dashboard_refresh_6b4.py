"""STATE-SUPERVISION-DASHBOARD-REFRESH-6B4: obnova termínových ploch po uložení."""

from __future__ import annotations

import importlib
import inspect
import os
import unittest
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()
_TODAY = date.today()
_NOW = datetime.combine(_TODAY, datetime.min.time().replace(hour=10))
_FUTURE = _NOW + timedelta(days=5)
_FUTURE_MOVED = _NOW + timedelta(days=12)
_PAST = _NOW - timedelta(days=4)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import ITEM_TYPE_STATE_SUPERVISION, ITEM_TYPE_TASK
    from core.dashboard.attention_service import (
        count_overdue_attention_items,
        get_attention_items,
        get_state_supervision_reminder_items,
    )
    from core.dashboard.widget_summary import SummaryWidget
    from core.dashboard.widget_today import TodayWidget
    from core.dashboard.widget_upcoming_tasks import COL_TYPE, UpcomingTasksWidget
    from core.models.attachment_staging import AttachmentStagingError
    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.widgets.editor_dialog_controller import EditorDialogController
    from moduly.agenda.sluzby import agenda_service as agenda_module
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        COL_RESULT,
        COL_STATUS,
        FILTER_MODE_ACTIVE,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
        WORKSPACE_REFRESH_FAILED_MESSAGE,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_deadline_projection import (
        KIND_FINDING,
        KIND_OBJECTIONS,
        KIND_PLANNED_START,
        document_identity,
        planned_start_identity,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab
    from moduly.statni_dozor.ui.state_supervision_table import STATUS_CUBE_ALERT_COLOR
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _ss_items(*, today: date = _TODAY):
    return [
        item
        for item in get_attention_items(today=today)
        if item.item_type == ITEM_TYPE_STATE_SUPERVISION
    ]


def _kinds_for(supervision_id: int, *, today: date = _TODAY):
    return {
        (item.open_metadata or {}).get("kind")
        for item in _ss_items(today=today)
        if item.source_id == supervision_id
    }


def _reminder_keys(*records, today: date = _TODAY):
    wanted = {int(record.id) for record in records}
    return {
        item.identity_key
        for item in get_state_supervision_reminder_items(today=today)
        if item.source_id in wanted
    }


def _upcoming_payloads(widget: UpcomingTasksWidget):
    rows = []
    for row in range(widget.table.rowCount()):
        cell = widget.table.item(row, COL_TYPE)
        if cell is None:
            continue
        rows.append(cell.data(Qt.ItemDataRole.UserRole))
    return rows


class StateSupervisionDashboardRefresh6B4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _supervision(self, **fields):
        payload = {
            "authority_name": f"OIP {self.marker}",
            "workplace_name_snapshot": f"Provoz {self.marker}",
            "subject": f"Předmět {self.marker}",
        }
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _page(self):
        page = AgendaPage()
        tab_calls: list[int | None] = []
        dash_calls: list[int] = []
        tab = page.state_supervision_tab
        original = tab.refresh

        def wrapped(*, select_id=None):
            tab_calls.append(select_id)
            return original(select_id=select_id)

        tab.refresh = wrapped  # type: ignore[method-assign]
        page.set_dashboard_refresh_callback(lambda: dash_calls.append(1))
        return page, tab_calls, dash_calls

    def _run_in_editor(self, tab: StateSupervisionTab, supervision_id: int, action):
        def fake_exec(dialog):
            action(dialog)
            return dialog.result()

        with patch(
            "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
            side_effect=fake_exec,
        ):
            tab._open_editor(supervision_id)

    def _overview_ids(self, tab: StateSupervisionTab) -> list[int]:
        ids = []
        for row in range(tab.table.rowCount()):
            if tab.table.isRowHidden(row):
                continue
            cell = tab.table.item(row, COL_STATUS)
            if cell is None:
                continue
            ids.append(int(cell.data(Qt.ItemDataRole.UserRole)))
        return ids

    def _status_item(self, tab: StateSupervisionTab, supervision_id: int):
        for row in range(tab.table.rowCount()):
            cell = tab.table.item(row, COL_STATUS)
            if cell is None:
                continue
            if int(cell.data(Qt.ItemDataRole.UserRole)) == int(supervision_id):
                return cell
        return None

    def test_01_save_stays_open_one_overview_and_dashboard_refresh(self) -> None:
        record = self._supervision()
        page, tab_calls, dash_calls = self._page()
        ss_index = page.tabs.indexOf(page.state_supervision_tab)
        page.tabs.setCurrentIndex(ss_index)

        def action(dialog):
            dialog.file_number_edit.setText(f"ULOZIT-{self.marker}")
            self.assertTrue(dialog._editor._run_save())
            self.assertFalse(dialog._editor.is_dirty())
            self.assertFalse(dialog._editor.save_button.isEnabled())
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            dialog.close()

        self._run_in_editor(page.state_supervision_tab, record.id, action)
        self.assertEqual(tab_calls, [record.id])
        self.assertEqual(dash_calls, [1])
        self.assertEqual(page.tabs.currentIndex(), ss_index)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.file_number, f"ULOZIT-{self.marker}")
        page.close()

    def test_02_save_and_close_one_refresh_no_second_after_exec(self) -> None:
        record = self._supervision()
        page, tab_calls, dash_calls = self._page()

        def action(dialog):
            dialog.file_number_edit.setText(f"ZAVRIT-{self.marker}")
            dialog._save_and_close()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

        self._run_in_editor(page.state_supervision_tab, record.id, action)
        self.assertEqual(tab_calls, [record.id])
        self.assertEqual(dash_calls, [1])
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).file_number,
            f"ZAVRIT-{self.marker}",
        )
        page.close()

    def test_03_close_then_save_one_refresh_and_closes(self) -> None:
        record = self._supervision()
        page, tab_calls, dash_calls = self._page()

        def action(dialog):
            dialog.file_number_edit.setText(f"PROMPT-{self.marker}")
            with patch(
                "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
                return_value="save",
            ):
                dialog._editor._handle_close_clicked()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

        self._run_in_editor(page.state_supervision_tab, record.id, action)
        self.assertEqual(tab_calls, [record.id])
        self.assertEqual(dash_calls, [1])
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).file_number,
            f"PROMPT-{self.marker}",
        )
        page.close()

    def test_04_no_refresh_on_cancel_discard_validation_and_save_errors(self) -> None:
        record = self._supervision()
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            record.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Otevřené {self.marker}",
            status=FINDING_STATUS_OTEVRENE,
        )
        page, tab_calls, dash_calls = self._page()
        tab = page.state_supervision_tab

        def cancel_action(dialog):
            dialog.file_number_edit.setText("zrusit")
            with patch(
                "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
                return_value="cancel",
            ):
                self.assertFalse(dialog._editor.request_close())
            self.assertTrue(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(tab, record.id, cancel_action)

        def discard_action(dialog):
            dialog.file_number_edit.setText("neukladat")
            with patch(
                "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
                return_value="discard",
            ):
                self.assertTrue(dialog._editor.request_close())
            dialog.close()

        self._run_in_editor(tab, record.id, discard_action)

        def validation_action(dialog):
            dialog.authority_combo.setCurrentText("")
            with patch.object(QMessageBox, "warning"):
                self.assertFalse(dialog._editor._run_save())
            self.assertTrue(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(tab, record.id, validation_action)

        def closure_cancel_action(dialog):
            dialog.status_combo.setCurrentIndex(
                dialog.status_combo.findData(STATUS_CLOSED)
            )
            dialog.closed_at_edit.set_datetime(_NOW)
            with (
                patch(
                    "moduly.statni_dozor.ui.state_supervision_editor_dialog."
                    "confirm_supervision_closure",
                    return_value=False,
                ),
                patch.object(QMessageBox, "warning"),
            ):
                self.assertFalse(dialog._editor._run_save())
            self.assertTrue(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(tab, record.id, closure_cancel_action)

        def bundle_fail(dialog):
            dialog.file_number_edit.setText("bundle")
            with (
                patch.object(
                    state_supervision_service,
                    "save_supervision_bundle",
                    side_effect=StateSupervisionError("bundle selhal"),
                ),
                patch.object(QMessageBox, "warning"),
                self.assertLogs(
                    "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                    level="ERROR",
                ),
            ):
                self.assertFalse(dialog._editor._run_save())
            self.assertTrue(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(tab, record.id, bundle_fail)

        def attachment_fail(dialog):
            dialog.file_number_edit.setText("priloha")
            with (
                patch.object(
                    state_supervision_service,
                    "save_supervision_bundle",
                    side_effect=AttachmentStagingError("příloha selhala"),
                ),
                patch.object(QMessageBox, "warning"),
                self.assertLogs(
                    "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                    level="ERROR",
                ),
            ):
                self.assertFalse(dialog._editor._run_save())
            self.assertTrue(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(tab, record.id, attachment_fail)

        def commit_fail(dialog):
            dialog.file_number_edit.setText("commit")
            with (
                patch.object(Session, "commit", side_effect=RuntimeError("db")),
                patch.object(QMessageBox, "warning"),
                self.assertLogs(
                    "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                    level="ERROR",
                ),
            ):
                self.assertFalse(dialog._editor._run_save())
            self.assertTrue(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(tab, record.id, commit_fail)

        self.assertEqual(tab_calls, [])
        self.assertEqual(dash_calls, [])
        self.assertIsNone(state_supervision_service.get_supervision(record.id).file_number)
        page.close()

    def test_05_open_editor_without_save_does_not_refresh(self) -> None:
        record = self._supervision()
        page, tab_calls, dash_calls = self._page()

        def action(dialog):
            self.assertFalse(dialog._editor.is_dirty())
            dialog.close()

        self._run_in_editor(page.state_supervision_tab, record.id, action)
        self.assertEqual(tab_calls, [])
        self.assertEqual(dash_calls, [])
        page.close()

    def test_06_visible_deadline_surfaces_update_after_save(self) -> None:
        record = self._supervision()
        page, tab_calls, dash_calls = self._page()
        upcoming = UpcomingTasksWidget()
        today_widget = TodayWidget()
        summary = SummaryWidget()

        def refresh_surfaces():
            dash_calls.append(1)
            upcoming.refresh()
            today_widget.refresh()
            summary.refresh()

        page.set_dashboard_refresh_callback(refresh_surfaces)
        tab = page.state_supervision_tab
        tab.refresh()
        tab_calls.clear()
        dash_calls.clear()
        overdue_before = int(summary.overdue.value_label.text())

        def add_start(dialog):
            dialog.planned_start_at_edit.set_datetime(_FUTURE)
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, add_start)
        self.assertEqual(tab_calls, [record.id])
        self.assertEqual(len(dash_calls), 1)
        self.assertIn(KIND_PLANNED_START, _kinds_for(record.id))
        self.assertTrue(
            any(
                getattr(item, "identity_key", None) == planned_start_identity(record.id)
                for item in _upcoming_payloads(upcoming)
            )
        )

        def move_start(dialog):
            dialog.planned_start_at_edit.set_datetime(_FUTURE_MOVED)
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, move_start)
        moved = next(
            item
            for item in _ss_items()
            if item.identity_key == planned_start_identity(record.id)
        )
        self.assertEqual(moved.date, _FUTURE_MOVED.date())

        def start_control(dialog):
            dialog.started_at_edit.set_datetime(_NOW)
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, start_control)
        self.assertNotIn(KIND_PLANNED_START, _kinds_for(record.id))

        def add_objections(dialog):
            dialog.objections_due_at_edit.set_datetime(_FUTURE)
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, add_objections)
        self.assertIn(KIND_OBJECTIONS, _kinds_for(record.id))

        def submit_objections(dialog):
            dialog.objections_submitted_at_edit.set_datetime(_NOW)
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, submit_objections)
        self.assertNotIn(KIND_OBJECTIONS, _kinds_for(record.id))

        def add_today_document(dialog):
            draft = StateSupervisionRequiredDocumentDraft(
                title=f"Dnešní {self.marker}",
                due_at=_NOW,
            )
            dialog._document_drafts.append(draft)
            dialog._refresh_documents_table(select_key=draft.client_key)
            dialog._editor.refresh_dirty()
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, add_today_document)
        stored_docs = [
            item
            for item in _reminder_keys(record)
            if item.startswith(f"ss:{record.id}:doc:")
        ]
        self.assertEqual(len(stored_docs), 1)
        self.assertIn(stored_docs[0], today_widget.content.text())

        doc_id = int(stored_docs[0].rsplit(":", 1)[-1])

        def submit_document(dialog):
            index = next(i for i, item in enumerate(dialog._document_drafts) if item.id == doc_id)
            dialog._document_drafts[index].submitted_at = _NOW
            dialog._refresh_documents_table()
            dialog._editor.refresh_dirty()
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, submit_document)
        self.assertNotIn(document_identity(record.id, doc_id), _reminder_keys(record))

        def add_finding(dialog):
            draft = StateSupervisionFindingDraft(
                finding_type=FINDING_TYPE_ZAVADA,
                description=f"Bez úkolu {self.marker}",
                status=FINDING_STATUS_OTEVRENE,
                due_date=_TODAY - timedelta(days=1),
            )
            dialog._findings_drafts.append(draft)
            dialog._refresh_findings_table(select_key=draft.client_key)
            dialog._editor.refresh_dirty()
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, add_finding)
        finding_keys = [
            item.identity_key
            for item in _ss_items()
            if item.source_id == record.id
            and (item.open_metadata or {}).get("kind") == KIND_FINDING
        ]
        self.assertEqual(len(finding_keys), 1)
        finding_id = int(finding_keys[0].rsplit(":", 1)[-1])
        overdue_with_finding = int(summary.overdue.value_label.text())
        self.assertGreaterEqual(overdue_with_finding, overdue_before)

        def resolve_finding(dialog):
            index = next(i for i, item in enumerate(dialog._findings_drafts) if item.id == finding_id)
            dialog._findings_drafts[index].status = FINDING_STATUS_VYPORADANO
            dialog._findings_drafts[index].resolved_at = _TODAY
            dialog._refresh_findings_table()
            dialog._editor.refresh_dirty()
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, resolve_finding)
        self.assertNotIn(KIND_FINDING, _kinds_for(record.id))
        self.assertEqual(
            int(summary.overdue.value_label.text()),
            count_overdue_attention_items(today=_TODAY),
        )

        def set_result_and_overdue_start(dialog):
            dialog.result_combo.setCurrentText("Pokuta")
            dialog.planned_start_at_edit.set_datetime(_PAST)
            dialog.started_at_edit.set_datetime(None)
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, record.id, set_result_and_overdue_start)
        result_cell = None
        for row in range(tab.table.rowCount()):
            status_cell = tab.table.item(row, COL_STATUS)
            if status_cell is None:
                continue
            if int(status_cell.data(Qt.ItemDataRole.UserRole)) == record.id:
                result_cell = tab.table.item(row, COL_RESULT)
                break
        self.assertIsNotNone(result_cell)
        self.assertEqual(result_cell.text(), "Pokuta")
        cube = self._status_item(tab, record.id)
        self.assertIsNotNone(cube)
        self.assertEqual(cube.background().color(), QColor(STATUS_CUBE_ALERT_COLOR))
        upcoming.close()
        today_widget.close()
        summary.close()
        page.close()

    def test_07_selection_filters_and_main_tab_stay(self) -> None:
        visible = self._supervision(authority_name=f"Viditelná {self.marker}")
        page, tab_calls, dash_calls = self._page()
        tab = page.state_supervision_tab
        ss_index = page.tabs.indexOf(tab)
        page.tabs.setCurrentIndex(ss_index)
        tab.mode_filter.setCurrentText(FILTER_MODE_ACTIVE)
        tab.refresh()
        tab.select_id = None
        tab.table.select_by_id(visible.id)
        tab_calls.clear()
        dash_calls.clear()
        filter_before = tab.mode_filter.currentText()

        def keep_visible(dialog):
            dialog.file_number_edit.setText("zustane")
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, visible.id, keep_visible)
        self.assertEqual(tab.table.selected_supervision_id(), visible.id)
        self.assertEqual(tab.mode_filter.currentText(), filter_before)
        self.assertEqual(page.tabs.currentIndex(), ss_index)

        hidden = self._supervision(authority_name=f"Skrytá {self.marker}")
        tab.refresh()
        tab.table.select_by_id(hidden.id)
        tab_calls.clear()
        dash_calls.clear()

        def hide_by_status(dialog):
            dialog.status_combo.setCurrentIndex(
                dialog.status_combo.findData(STATUS_CANCELLED)
            )
            self.assertTrue(dialog._editor._run_save())
            dialog.close()

        self._run_in_editor(tab, hidden.id, hide_by_status)
        self.assertEqual(tab.mode_filter.currentText(), FILTER_MODE_ACTIVE)
        self.assertNotIn(hidden.id, self._overview_ids(tab))
        self.assertNotEqual(tab.table.selected_supervision_id(), hidden.id)
        self.assertEqual(page.tabs.currentIndex(), ss_index)
        self.assertEqual(tab_calls, [hidden.id])
        self.assertEqual(dash_calls, [1])
        page.close()

    def test_08_refresh_error_keeps_saved_data_clean_editor_and_no_second_save(self) -> None:
        record = self._supervision()
        dialog = StateSupervisionEditorDialog(
            on_saved=lambda _sid: (_ for _ in ()).throw(RuntimeError("refresh boom"))
        )
        dialog.authority_combo.setCurrentText(f"Chyba refresh {self.marker}")
        with (
            patch.object(
                state_supervision_service,
                "save_supervision_bundle",
                wraps=state_supervision_service.save_supervision_bundle,
            ) as save,
            patch.object(QMessageBox, "information") as info,
            patch.object(QMessageBox, "warning") as warn,
            self.assertLogs(
                "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                level="ERROR",
            ),
        ):
            self.assertTrue(dialog._editor._run_save())
        self.assertEqual(save.call_count, 1)
        warn.assert_not_called()
        info.assert_called()
        self.assertEqual(info.call_args[0][2], WORKSPACE_REFRESH_FAILED_MESSAGE)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.authority_name, f"Chyba refresh {self.marker}")
        self.assertNotEqual(loaded.id, record.id)
        dialog.close()

        existing = StateSupervisionEditorDialog(
            supervision_id=record.id,
            on_saved=lambda _sid: (_ for _ in ()).throw(RuntimeError("close boom")),
        )
        existing.file_number_edit.setText("po-chybě-refresh")
        with (
            patch.object(QMessageBox, "information") as info_close,
            self.assertLogs(
                "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                level="ERROR",
            ),
        ):
            existing._save_and_close()
        self.assertEqual(existing.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(info_close.call_args[0][2], WORKSPACE_REFRESH_FAILED_MESSAGE)
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).file_number,
            "po-chybě-refresh",
        )
        existing.close()

    def test_09_finding_task_keeps_single_existing_refresh(self) -> None:
        parent = self._supervision()
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Úkol {self.marker}",
            status=FINDING_STATUS_OTEVRENE,
        )
        page, tab_calls, dash_calls = self._page()
        ss_index = page.tabs.indexOf(page.state_supervision_tab)
        page.tabs.setCurrentIndex(ss_index)
        dialog = StateSupervisionEditorDialog(
            page.state_supervision_tab,
            supervision_id=parent.id,
            on_saved=page.state_supervision_tab.state_supervision_saved,
        )
        dialog._select_finding_key(f"db-{int(finding.id)}")
        dialog._refresh_finding_actions()

        def accept_task(self):
            data = dict(self.get_data())
            if self._create_factory is not None:
                self.task = self._create_factory(data)
            return QDialog.DialogCode.Accepted

        with patch.object(TaskDialog, "exec", accept_task):
            dialog._create_finding_task()
        self.assertEqual(page.tabs.currentIndex(), ss_index)
        self.assertEqual(dash_calls, [1])
        self.assertEqual(tab_calls, [])
        created_id = finding_service.get_by_id(finding.id).task_id
        titles = [item.title for item in agenda_service.get_items() if item.source_id == created_id]
        self.assertEqual(len(titles), 1)
        attention_tasks = [
            item
            for item in get_attention_items()
            if item.item_type == ITEM_TYPE_TASK and item.source_id == created_id
        ]
        self.assertEqual(len(attention_tasks), 1)
        dialog.close()
        page.close()

    def test_10_regression_contract(self) -> None:
        editor = inspect.getsource(StateSupervisionEditorDialog)
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        tab_src = inspect.getsource(StateSupervisionTab)
        open_src = inspect.getsource(StateSupervisionTab._open_editor)
        notify = inspect.getsource(StateSupervisionEditorDialog._notify_state_supervision_saved)
        page_src = inspect.getsource(AgendaPage)
        from core.dashboard import widget_calendar_placeholder

        self.assertIn("on_saved", inspect.signature(StateSupervisionEditorDialog.__init__).parameters)
        self.assertIn("state_supervision_saved", tab_src)
        self.assertIn("on_saved", open_src)
        self.assertNotIn("if dialog.saved", open_src)
        self.assertIn("_notify_state_supervision_saved", editor)
        self.assertNotIn("save_supervision_bundle", notify)
        self.assertNotIn("event_bus", editor.lower() + tab_src.lower() + page_src.lower())
        self.assertNotIn("EventBus", editor + tab_src + page_src)
        self.assertIn("refresh_dashboard", page_src)
        self.assertNotIn("state_supervision", inspect.getsource(agenda_module))
        self.assertNotIn(
            "state_supervision",
            inspect.getsource(widget_calendar_placeholder),
        )
        self.assertIn("widget.refresh_dashboard()", inspect.getsource(
            StateSupervisionEditorDialog._notify_agenda_task_created
        ))
        self.assertIn("widget.refresh()", inspect.getsource(
            StateSupervisionEditorDialog._notify_agenda_task_created
        ))
        self.assertNotIn("state_supervision_saved", persist)
        self.assertNotIn("refresh_dashboard", persist)
        self.assertNotIn("_notify_state_supervision_saved", persist)

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        page.close()
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


if __name__ == "__main__":
    unittest.main()
