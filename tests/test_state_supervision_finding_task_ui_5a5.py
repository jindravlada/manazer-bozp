"""STATE-SUPERVISION-FINDING-TASK-UI-5A5: navazující úkol ze zjištění."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import ITEM_TYPE_TASK
    from core.dashboard.attention_service import get_attention_items
    from core.navigation.source_navigator import source_navigator
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_FINDING,
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from core.widgets.editor_dialog_controller import EditorDialogController
    from core.widgets.finding_task_actions import FindingTaskActions
    from moduly.agenda.constants import PRIORITY_CRITICAL, PRIORITY_LOW
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.statni_dozor.constants import (
        ACTION_CREATE_TASK,
        ACTION_OPEN_TASK,
        COL_FINDING_TASK,
        EMPTY_VALUE,
        FILTER_MODE_ACTIVE,
        FINDING_TASK_DIRTY_TOOLTIP,
        FINDING_TASK_HINT_DIRTY,
        FINDING_TASK_HINT_LINKED,
        FINDING_TASK_HINT_UNSAVED,
        FINDING_TASK_MISSING_LABEL,
        FINDING_TASK_MISSING_OPEN_MESSAGE,
        FINDING_TASK_RELOAD_FAILED_MESSAGE,
        FINDING_TASK_SAVE_FIRST_TOOLTIP,
        GROUP_FINDINGS,
        STATUS_CLOSED,
        TAB_STATE_SUPERVISION,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_task_service import (
        state_supervision_finding_task_service as ss_finding_task_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


class StateSupervisionFindingTaskUi5a5TestCase(unittest.TestCase):
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
        source_navigator.configure(None)
        self.worker = settings_service.save_worker(
            first_name="Eva",
            last_name=f"THP-{self.marker}",
        )

    def tearDown(self) -> None:
        source_navigator.configure(None)

    def _supervision(self, **fields):
        payload = {
            "authority_name": f"OIP {self.marker}",
            "subject": "BOZP na pracovišti",
        }
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _ss_finding(self, parent_id: int, **fields):
        payload = {
            "finding_type": FINDING_TYPE_ZAVADA,
            "description": f"Zjištění {self.marker}",
            "status": FINDING_STATUS_OTEVRENE,
        }
        payload.update(fields)
        return finding_service.create(ENTITY_STATE_SUPERVISION, parent_id, **payload)

    def _open_editor(self, supervision_id: int, parent=None) -> StateSupervisionEditorDialog:
        return StateSupervisionEditorDialog(parent, supervision_id=supervision_id)

    def _select_stored(self, dialog: StateSupervisionEditorDialog, finding_id: int):
        dialog._select_finding_key(f"db-{int(finding_id)}")
        dialog._refresh_finding_actions()

    def _accept_task_dialog(self, *, tamper_priority: bool = False):
        def _exec(self):
            data = dict(self.get_data())
            if tamper_priority:
                data["priority"] = PRIORITY_LOW
            if self._create_factory is not None:
                self.task = self._create_factory(data)
            return (
                QDialog.DialogCode.Accepted
                if getattr(self, "task", None) is not None
                else QDialog.DialogCode.Rejected
            )

        return _exec

    def test_01_button_states(self) -> None:
        parent = self._supervision()
        stored = self._ss_finding(parent.id, description="Bez úkolu")
        linked = self._ss_finding(parent.id, description="S úkolem")
        task = ss_finding_task_service.create_task_for_finding(linked.id)
        missing = self._ss_finding(parent.id, description="Chybějící úkol", task_id=9_999_111)

        dialog = self._open_editor(parent.id)
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertFalse(dialog.open_finding_task_btn.isEnabled())
        self.assertEqual(dialog.create_finding_task_btn.text(), ACTION_CREATE_TASK)
        self.assertEqual(dialog.open_finding_task_btn.text(), ACTION_OPEN_TASK)
        self.assertTrue(dialog.finding_task_hint_label.isHidden())

        draft = StateSupervisionFindingDraft(
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Nový draft",
            client_key=f"new-{self.marker}",
        )
        dialog._findings_drafts.append(draft)
        dialog._refresh_findings_table(select_key=draft.client_key)
        dialog._editor.capture_baseline()
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertFalse(dialog.open_finding_task_btn.isEnabled())
        self.assertEqual(
            dialog.create_finding_task_btn.toolTip(),
            FINDING_TASK_SAVE_FIRST_TOOLTIP,
        )
        self.assertEqual(dialog.finding_task_hint_label.text(), FINDING_TASK_HINT_UNSAVED)
        self.assertFalse(dialog.finding_task_hint_label.isHidden())

        self._select_stored(dialog, stored.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertTrue(dialog.create_finding_task_btn.isEnabled())
        self.assertFalse(dialog.open_finding_task_btn.isEnabled())
        self.assertEqual(dialog.create_finding_task_btn.toolTip(), "")
        self.assertTrue(dialog.finding_task_hint_label.isHidden())

        original_subject = dialog.subject_edit.toPlainText()
        dialog.subject_edit.setPlainText(original_subject + " změna")
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertFalse(dialog.open_finding_task_btn.isEnabled())
        self.assertIn("uložte všechny změny", dialog.create_finding_task_btn.toolTip())
        self.assertEqual(dialog.finding_task_hint_label.text(), FINDING_TASK_HINT_DIRTY)

        dialog.subject_edit.setPlainText(original_subject)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertTrue(dialog.create_finding_task_btn.isEnabled())
        self.assertFalse(dialog.open_finding_task_btn.isEnabled())

        self._select_stored(dialog, linked.id)
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertTrue(dialog.open_finding_task_btn.isEnabled())
        self.assertEqual(dialog.finding_task_hint_label.text(), FINDING_TASK_HINT_LINKED)
        dialog.subject_edit.setPlainText(original_subject + " dirty")
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertTrue(dialog.open_finding_task_btn.isEnabled())
        dialog.subject_edit.setPlainText(original_subject)
        dialog._editor.refresh_dirty()

        self._select_stored(dialog, missing.id)
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertTrue(dialog.open_finding_task_btn.isEnabled())
        self.assertEqual(
            dialog.findings_table.item(
                next(
                    i
                    for i, row in enumerate(dialog._findings_drafts)
                    if row.id == missing.id
                ),
                COL_FINDING_TASK,
            ).text(),
            FINDING_TASK_MISSING_LABEL,
        )
        self.assertEqual(task.priority, PRIORITY_CRITICAL)
        dialog.close()

    def test_02_create_prefill_locked_priority_and_factory(self) -> None:
        parent = self._supervision(authority_name="KHS Brno", subject="Hygiena")
        due = date(2026, 9, 20)
        finding = self._ss_finding(
            parent.id,
            description="Popis zjištění pro úkol",
            recommended_action="Doplnit OOPP",
            due_date=due,
            responsible_person_id=self.worker.id,
            responsible_person_name=f"Eva THP-{self.marker}",
        )
        dialog = self._open_editor(parent.id)
        self._select_stored(dialog, finding.id)
        self.assertFalse(dialog._editor.is_dirty())

        captured: dict = {}

        def inspect_exec(self):
            captured["title"] = self.title_edit.toPlainText()
            captured["priority"] = self.priority_combo.currentText()
            captured["priority_enabled"] = self.priority_combo.isEnabled()
            captured["fixed"] = self._fixed_priority
            captured["verification"] = self.requires_verification_checkbox.isChecked()
            captured["person"] = self.person_selector.current_person_id()
            captured["due"] = self.get_data()["due_date"]
            captured["factory"] = self._create_factory
            captured["source"] = self.source_panel.source_label.text()
            captured["description"] = self.source_panel.description_label.text()
            captured["open_hidden"] = self.source_panel.open_button.isHidden()
            captured["get_priority"] = self.get_data()["priority"]
            return QDialog.DialogCode.Rejected

        before = _count("tasks")
        with patch.object(TaskDialog, "exec", inspect_exec):
            dialog._create_finding_task()
        self.assertEqual(_count("tasks"), before)
        self.assertEqual(captured["title"], "Doplnit OOPP")
        self.assertEqual(captured["priority"], PRIORITY_CRITICAL)
        self.assertFalse(captured["priority_enabled"])
        self.assertEqual(captured["fixed"], PRIORITY_CRITICAL)
        self.assertTrue(captured["verification"])
        self.assertEqual(captured["person"], self.worker.id)
        self.assertEqual(captured["due"], due)
        self.assertIn("Státní dozor", captured["source"])
        self.assertIn("Popis zjištění pro úkol", captured["description"])
        self.assertTrue(captured["open_hidden"])
        self.assertEqual(captured["get_priority"], PRIORITY_CRITICAL)
        self.assertTrue(callable(captured["factory"]))
        self.assertFalse(dialog._editor.is_dirty())
        refreshed = finding_service.get_by_id(finding.id)
        self.assertIsNone(refreshed.task_id)

        with patch.object(TaskDialog, "exec", self._accept_task_dialog(tamper_priority=True)):
            dialog._create_finding_task()
        after = finding_service.get_by_id(finding.id)
        self.assertIsNotNone(after.task_id)
        created = task_service.get_task_by_id(after.task_id)
        self.assertEqual(created.priority, PRIORITY_CRITICAL)
        self.assertEqual(created.source_module, ENTITY_FINDING)
        self.assertEqual(created.source_record_id, finding.id)
        self.assertEqual(created.responsible_person_id, self.worker.id)
        self.assertEqual(created.due_date, due)
        self.assertTrue(created.requires_verification)
        self.assertEqual(_count("tasks"), before + 1)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertTrue(dialog.open_finding_task_btn.isEnabled())
        row = next(i for i, item in enumerate(dialog._findings_drafts) if item.id == finding.id)
        self.assertEqual(
            dialog.findings_table.item(row, COL_FINDING_TASK).text(),
            created.title,
        )
        tooltip = dialog.findings_table.item(row, COL_FINDING_TASK).toolTip()
        self.assertIn(created.title, tooltip)
        self.assertIn(created.computed_status, tooltip)
        self.assertIn("20.09.2026", tooltip.replace(" ", ""))

        with patch.object(TaskDialog, "exec", self._accept_task_dialog()):
            dialog._create_finding_task()
        self.assertEqual(_count("tasks"), before + 1)
        dialog.close()

        unlocked = TaskDialog()
        self.assertTrue(unlocked.priority_combo.isEnabled())
        self.assertEqual(unlocked.priority_combo.currentText(), "Normální")
        self.assertIsNone(unlocked._fixed_priority)
        unlocked.close()

    def test_03_cancel_error_dirty_and_no_autosave(self) -> None:
        parent = self._supervision()
        finding = self._ss_finding(parent.id, description="Dirty tok")
        dialog = self._open_editor(parent.id)
        self._select_stored(dialog, finding.id)
        before = _count("tasks")

        with patch.object(TaskDialog, "exec", lambda self: QDialog.DialogCode.Rejected):
            dialog._create_finding_task()
        self.assertEqual(_count("tasks"), before)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)
        self.assertFalse(dialog._editor.is_dirty())

        dialog.subject_edit.setPlainText("rozpracováno")
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        opened: list[int] = []

        def spy_exec(self):
            opened.append(1)
            return QDialog.DialogCode.Rejected

        persist_calls: list[int] = []
        original_persist = dialog._persist

        def spy_persist():
            persist_calls.append(1)
            return original_persist()

        dialog._persist = spy_persist  # type: ignore[method-assign]
        with patch.object(TaskDialog, "exec", spy_exec):
            dialog._create_finding_task()
        self.assertEqual(opened, [])
        self.assertEqual(persist_calls, [])
        self.assertEqual(_count("tasks"), before)
        self.assertTrue(dialog._editor.is_dirty())

        dialog.subject_edit.setPlainText("BOZP na pracovišti")
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        with (
            patch.object(
                ss_finding_task_service,
                "create_task_for_finding",
                side_effect=StateSupervisionError("Nelze vytvořit úkol."),
            ),
            patch.object(QMessageBox, "warning") as warn,
            patch.object(TaskDialog, "exec", self._accept_task_dialog()),
        ):
            dialog._create_finding_task()
        self.assertEqual(_count("tasks"), before)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)
        warn.assert_called()
        self.assertIn("Nelze vytvořit úkol.", warn.call_args[0][2])
        dialog.close()

    def test_04_open_task_and_missing_and_dirty_collection(self) -> None:
        parent = self._supervision()
        finding = self._ss_finding(parent.id, description="Otevřít existující")
        task = ss_finding_task_service.create_task_for_finding(finding.id)
        dangling = self._ss_finding(parent.id, description="Bez Task", task_id=8_888_222)
        dialog = self._open_editor(parent.id)
        extra = StateSupervisionFindingDraft(
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Pracovní změna",
            client_key=f"work-{self.marker}",
        )
        dialog._findings_drafts.append(extra)
        dialog._refresh_findings_table()
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        self._select_stored(dialog, finding.id)

        captured: dict = {}

        def open_exec(self):
            captured["task_id"] = getattr(self.task, "id", None)
            captured["factory"] = self._create_factory
            return QDialog.DialogCode.Rejected

        drafts_before = [item.client_key for item in dialog._findings_drafts]
        with patch.object(TaskDialog, "exec", open_exec):
            dialog._open_finding_task()
        self.assertEqual(captured["task_id"], task.id)
        self.assertIsNone(captured["factory"])
        self.assertEqual(
            [item.client_key for item in dialog._findings_drafts],
            drafts_before,
        )
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(any(item.client_key == extra.client_key for item in dialog._findings_drafts))

        self._select_stored(dialog, dangling.id)
        with patch.object(QMessageBox, "warning") as warn:
            dialog._open_finding_task()
        self.assertEqual(warn.call_args[0][2], FINDING_TASK_MISSING_OPEN_MESSAGE)
        still = next(item for item in dialog._findings_drafts if item.id == dangling.id)
        self.assertEqual(still.task_id, 8_888_222)
        self.assertTrue(any(item.client_key == extra.client_key for item in dialog._findings_drafts))
        dialog.close()

    def test_05_table_batch_load_and_dash(self) -> None:
        parent = self._supervision()
        empty = self._ss_finding(parent.id, description="Bez vazby")
        first = self._ss_finding(parent.id, description="První s úkolem")
        second = self._ss_finding(parent.id, description="Druhé s úkolem")
        task_a = ss_finding_task_service.create_task_for_finding(first.id)
        task_b = ss_finding_task_service.create_task_for_finding(second.id)
        missing = self._ss_finding(parent.id, description="Navázáno mimo", task_id=7_777_333)

        with (
            patch.object(task_service, "get_tasks_by_ids", wraps=task_service.get_tasks_by_ids) as batched,
            patch.object(task_service, "get_task_by_id", wraps=task_service.get_task_by_id) as one,
        ):
            dialog = self._open_editor(parent.id)
            batched.assert_called()
            self.assertEqual(batched.call_count, 1)
            one.assert_not_called()
        by_id = {item.id: item for item in dialog._findings_drafts}
        empty_row = next(i for i, item in enumerate(dialog._findings_drafts) if item.id == empty.id)
        first_row = next(i for i, item in enumerate(dialog._findings_drafts) if item.id == first.id)
        missing_row = next(i for i, item in enumerate(dialog._findings_drafts) if item.id == missing.id)
        self.assertEqual(dialog.findings_table.item(empty_row, COL_FINDING_TASK).text(), EMPTY_VALUE)
        self.assertEqual(dialog.findings_table.item(first_row, COL_FINDING_TASK).text(), task_a.title)
        self.assertNotIn(str(task_a.id), dialog.findings_table.item(first_row, COL_FINDING_TASK).text())
        self.assertEqual(
            dialog.findings_table.item(missing_row, COL_FINDING_TASK).text(),
            FINDING_TASK_MISSING_LABEL,
        )
        self.assertIn(task_b.title, dialog.findings_table.item(
            next(i for i, item in enumerate(dialog._findings_drafts) if item.id == second.id),
            COL_FINDING_TASK,
        ).text())
        self.assertEqual(by_id[first.id].task_id, task_a.id)
        dialog.close()

    def test_06_reload_failure_keeps_link(self) -> None:
        parent = self._supervision()
        finding = self._ss_finding(parent.id, description="Reload selže")
        dialog = self._open_editor(parent.id)
        self._select_stored(dialog, finding.id)
        before = _count("tasks")
        with (
            patch.object(dialog, "_load_findings", side_effect=RuntimeError("boom")),
            patch.object(QMessageBox, "warning") as warn,
            patch.object(TaskDialog, "exec", self._accept_task_dialog()),
        ):
            dialog._create_finding_task()
        self.assertEqual(_count("tasks"), before + 1)
        linked = next(item for item in dialog._findings_drafts if item.id == finding.id)
        self.assertIsNotNone(linked.task_id)
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertTrue(dialog.open_finding_task_btn.isEnabled())
        self.assertIn(FINDING_TASK_RELOAD_FAILED_MESSAGE, warn.call_args[0][2])
        dialog.close()

    def test_07_agenda_dashboard_refresh_and_source_navigation(self) -> None:
        parent = self._supervision(authority_name="OIP Praha", subject="Sklad")
        finding = self._ss_finding(parent.id, description="Agenda refresh")
        page = AgendaPage()
        dashboard_calls: list[int] = []
        page.set_dashboard_refresh_callback(lambda: dashboard_calls.append(1))
        ss_index = page.tabs.indexOf(page.state_supervision_tab)
        page.tabs.setCurrentIndex(ss_index)
        dialog = self._open_editor(parent.id, parent=page.state_supervision_tab)
        self._select_stored(dialog, finding.id)
        with patch.object(TaskDialog, "exec", self._accept_task_dialog()):
            dialog._create_finding_task()
        self.assertEqual(page.tabs.currentIndex(), ss_index)
        self.assertEqual(page.tabs.tabText(ss_index), TAB_STATE_SUPERVISION)
        self.assertTrue(dashboard_calls)
        created_id = finding_service.get_by_id(finding.id).task_id
        items = agenda_service.get_items()
        found = next(item for item in items if item.source_id == created_id)
        self.assertEqual(found.source, "Státní dozor")
        self.assertEqual(found.priority, PRIORITY_CRITICAL)
        page.refresh()
        from moduly.agenda.constants import COL_TITLE

        titles = [
            page.table.item(row, COL_TITLE).text()
            for row in range(page.table.rowCount())
            if page.table.item(row, COL_TITLE) is not None
        ]
        created = task_service.get_task_by_id(created_id)
        self.assertIn(created.title, titles)
        attention = get_attention_items()
        dash_item = next(
            item
            for item in attention
            if item.item_type == ITEM_TYPE_TASK and item.source_id == created_id
        )
        self.assertEqual(dash_item.priority, PRIORITY_CRITICAL)
        dialog.close()

        host = MagicMock()
        host._page_widgets = {"agenda": page}
        host._show = MagicMock()
        source_navigator.configure(host)
        opened: list[int | None] = []

        class FakeDialog:
            def __init__(self, parent=None, *, supervision_id=None):
                opened.append(supervision_id)
                self.saved = False
                self.supervision_id = supervision_id

        with (
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.StateSupervisionEditorDialog",
                FakeDialog,
            ),
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
                lambda dialog: None,
            ),
            patch.object(Session, "commit") as commit,
        ):
            task_dialog = TaskDialog(page, task=created)
            self.assertFalse(task_dialog.source_panel.open_button.isHidden())
            self.assertTrue(source_navigator.open_finding(finding.id))
            self.assertEqual(opened[-1], parent.id)
            task_dialog._open_source_record()
            self.assertEqual(opened[-1], parent.id)
            commit.assert_not_called()
            task_dialog.close()

        page.state_supervision_tab.mode_filter.setCurrentText(FILTER_MODE_ACTIVE)
        closed = self._supervision(
            status=STATUS_CLOSED,
            authority_name=f"Uzavřená {self.marker}",
            closed_at=datetime(2026, 3, 2, 9, 0, 0),
        )
        closed_finding = self._ss_finding(closed.id, description="Uzavřená navigace")
        with (
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.StateSupervisionEditorDialog",
                FakeDialog,
            ),
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
                lambda dialog: None,
            ),
        ):
            opened.clear()
            self.assertTrue(source_navigator.open_finding(closed_finding.id))
            self.assertEqual(opened[-1], closed.id)
        page.close()
        dialog.close()

    def test_08_no_automatic_task(self) -> None:
        parent = self._supervision()
        finding = self._ss_finding(parent.id, description="Bez automatu")
        before = _count("tasks")
        dialog = self._open_editor(parent.id)
        self.assertEqual(_count("tasks"), before)
        self._select_stored(dialog, finding.id)
        self.assertEqual(_count("tasks"), before)
        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=None,
        ):
            dialog._edit_selected_finding()
        self.assertEqual(_count("tasks"), before)
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("doubleClicked.connect(self._edit_selected_finding)", source)
        self.assertNotIn("doubleClicked.connect(self._create_finding_task)", source)
        self.assertTrue(dialog._editor._run_save())
        self.assertEqual(_count("tasks"), before)
        index = next(i for i, item in enumerate(dialog._findings_drafts) if item.id == finding.id)
        dialog._findings_drafts[index] = replace(
            dialog._findings_drafts[index],
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 9, 1),
        )
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor._run_save())
        self.assertEqual(_count("tasks"), before)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        self.assertNotIn("create_task_for_finding", persist)
        dialog.close()

    def test_09_regression_contract(self) -> None:
        editor_src = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_src.count("self.tabs.addTab("), 5)
        self.assertIn("create_factory", editor_src)
        self.assertIn("fixed_priority", inspect.getsource(TaskDialog))
        self.assertIn("source_finding", inspect.getsource(TaskDialog))
        self.assertNotIn("fixed_priority", inspect.getsource(FindingTaskActions))
        from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget
        from moduly.externi_audity.ui.external_audit_findings_widget import (
            ExternalAuditFindingsWidget,
        )
        from moduly.proverky.ui.bozp_inspection_findings_widget import (
            BozpInspectionFindingsWidget,
        )

        self.assertNotIn("fixed_priority", inspect.getsource(AuditFindingsWidget))
        self.assertNotIn("fixed_priority", inspect.getsource(BozpInspectionFindingsWidget))
        self.assertNotIn("PRIORITY_CRITICAL", inspect.getsource(ExternalAuditFindingsWidget))
        task_src = inspect.getsource(finding_task_service.__class__)
        self.assertNotIn("state_supervision", task_src)
        bundle = inspect.signature(StateSupervisionService.save_supervision_bundle)
        self.assertIn("findings", bundle.parameters)
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        self.assertIn("attachments=", persist)
        self.assertIn("participants=", persist)
        self.assertIn("timeline_items=", persist)
        self.assertIn("findings=", persist)
        probe = StateSupervisionEditorDialog()
        self.assertIsInstance(probe._editor, EditorDialogController)
        probe.close()
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        audit_finding = finding_service.create(
            ENTITY_AUDITY,
            88001,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Auditní bez Kritické",
        )
        audit_task = finding_task_service.create_task_from_finding(audit_finding.id)
        self.assertNotEqual(audit_task.priority, PRIORITY_CRITICAL)
        page.close()


if __name__ == "__main__":
    unittest.main()
