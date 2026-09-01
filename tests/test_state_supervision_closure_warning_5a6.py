"""STATE-SUPERVISION-CLOSURE-WARNING-5A6: upozornění při uzavření kontroly."""

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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
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
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.widgets.editor_dialog_controller import (
        EDITOR_CANCEL_LABEL,
        EditorDialogController,
    )
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_CONFIRM_CLOSE_SUPERVISION,
        CLOSED_AT_REQUIRED_MESSAGE,
        CLOSURE_WARNING_ACTIVE_TASKS,
        CLOSURE_WARNING_FOOTER,
        CLOSURE_WARNING_INTRO,
        CLOSURE_WARNING_MISSING_TASKS,
        CLOSURE_WARNING_OPEN_FINDINGS,
        STATUS_ANNOUNCED,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_IN_PROGRESS,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_closure_readiness import (
        StateSupervisionClosureReadiness,
        state_supervision_closure_readiness,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_closure_confirm import (
        confirm_supervision_closure,
        format_closure_warning_text,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.ukoly.constants import (
        TASK_STATUS_ACTIVE,
        TASK_STATUS_CANCELED,
        TASK_STATUS_CLOSED,
        TASK_STATUS_WAITING_CHECK,
    )
    from moduly.ukoly.sluzby.task_service import task_service


_CONFIRM = (
    "moduly.statni_dozor.ui.state_supervision_editor_dialog.confirm_supervision_closure"
)
_CLOSED_AT = datetime(2026, 5, 20, 12, 0, 0)


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _draft(**fields) -> StateSupervisionFindingDraft:
    payload = {
        "finding_type": FINDING_TYPE_ZJISTENI,
        "description": "Zjištění",
        "status": FINDING_STATUS_OTEVRENE,
    }
    payload.update(fields)
    return StateSupervisionFindingDraft(**payload)


def _fake_task(task_id: int, status: str) -> SimpleNamespace:
    return SimpleNamespace(id=task_id, computed_status=status)


class StateSupervisionClosureWarning5a6TestCase(unittest.TestCase):
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

    def _open_editor(self, supervision_id: int) -> StateSupervisionEditorDialog:
        return StateSupervisionEditorDialog(supervision_id=supervision_id)

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _prepare_close(self, dialog: StateSupervisionEditorDialog) -> None:
        dialog.status_combo.setCurrentIndex(dialog.status_combo.findData(STATUS_CLOSED))
        dialog.closed_at_edit.set_datetime(_CLOSED_AT)
        dialog._editor.refresh_dirty()

    def test_01_helper_empty_and_resolved_only(self) -> None:
        empty = state_supervision_closure_readiness([], load_tasks=lambda ids: [])
        self.assertEqual(empty.open_findings_count, 0)
        self.assertEqual(empty.active_tasks_count, 0)
        self.assertEqual(empty.missing_tasks_count, 0)
        self.assertFalse(empty.needs_confirmation)

        resolved = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, description="Hotovo")],
            load_tasks=lambda ids: [],
        )
        self.assertEqual(resolved.open_findings_count, 0)
        self.assertFalse(resolved.needs_confirmation)

    def test_02_helper_open_and_in_progress_findings(self) -> None:
        open_only = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_OTEVRENE, client_key="open-1")],
            load_tasks=lambda ids: [],
        )
        self.assertEqual(open_only.open_findings_count, 1)
        self.assertEqual(open_only.open_finding_keys, ("open-1",))
        self.assertTrue(open_only.needs_confirmation)

        in_progress = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_V_PROCESU, client_key="proc-1")],
            load_tasks=lambda ids: [],
        )
        self.assertEqual(in_progress.open_findings_count, 1)
        self.assertTrue(in_progress.needs_confirmation)

        mixed = state_supervision_closure_readiness(
            [
                _draft(status=FINDING_STATUS_OTEVRENE, client_key="a"),
                _draft(status=FINDING_STATUS_V_PROCESU, client_key="b"),
                _draft(status=FINDING_STATUS_VYPORADANO, client_key="c"),
            ],
            load_tasks=lambda ids: [],
        )
        self.assertEqual(mixed.open_findings_count, 2)
        self.assertEqual(mixed.open_finding_keys, ("a", "b"))

    def test_03_helper_task_states_and_missing(self) -> None:
        calls: list[list[int]] = []

        def load(ids):
            calls.append(list(ids))
            mapping = {
                1: _fake_task(1, TASK_STATUS_ACTIVE),
                2: _fake_task(2, TASK_STATUS_ACTIVE),
                3: _fake_task(3, TASK_STATUS_WAITING_CHECK),
                4: _fake_task(4, TASK_STATUS_CLOSED),
                5: _fake_task(5, TASK_STATUS_CANCELED),
            }
            return [mapping[i] for i in ids if i in mapping]

        active = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, task_id=1)],
            load_tasks=load,
        )
        self.assertEqual(active.open_findings_count, 0)
        self.assertEqual(active.active_tasks_count, 1)
        self.assertEqual(active.active_task_ids, (1,))

        overdue = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, task_id=2)],
            load_tasks=load,
        )
        self.assertEqual(overdue.active_tasks_count, 1)

        waiting = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, task_id=3)],
            load_tasks=load,
        )
        self.assertEqual(waiting.active_tasks_count, 1)
        self.assertNotIn(TASK_STATUS_WAITING_CHECK, {TASK_STATUS_CLOSED, TASK_STATUS_CANCELED})

        closed = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, task_id=4)],
            load_tasks=load,
        )
        self.assertEqual(closed.active_tasks_count, 0)
        self.assertFalse(closed.needs_confirmation)

        canceled = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, task_id=5)],
            load_tasks=load,
        )
        self.assertEqual(canceled.active_tasks_count, 0)
        self.assertFalse(canceled.needs_confirmation)

        missing = state_supervision_closure_readiness(
            [_draft(status=FINDING_STATUS_VYPORADANO, task_id=99)],
            load_tasks=load,
        )
        self.assertEqual(missing.missing_tasks_count, 1)
        self.assertEqual(missing.missing_task_ids, (99,))
        self.assertEqual(missing.active_tasks_count, 0)
        self.assertTrue(missing.needs_confirmation)

        batch = state_supervision_closure_readiness(
            [
                _draft(task_id=1, client_key="d1"),
                _draft(task_id=3, client_key="d2"),
                _draft(task_id=1, client_key="d3"),
                _draft(task_id=99, client_key="d4"),
                _draft(task_id=4, status=FINDING_STATUS_VYPORADANO, client_key="d5"),
            ],
            load_tasks=load,
        )
        self.assertEqual(batch.open_findings_count, 4)
        self.assertEqual(batch.active_tasks_count, 2)
        self.assertEqual(batch.missing_tasks_count, 1)
        self.assertEqual(calls[-1], [1, 3, 99, 4])

    def test_04_helper_batch_real_tasks_no_write(self) -> None:
        overdue = task_service.create_task(
            title=f"Po termínu {self.marker}",
            due_date=date(2020, 1, 1),
            requires_verification=False,
        )
        waiting = task_service.create_task(
            title=f"Kontrola {self.marker}",
            completed=True,
            requires_verification=True,
        )
        done = task_service.create_task(
            title=f"Ukončený {self.marker}",
            completed=True,
            requires_verification=False,
        )
        canceled = task_service.create_task(
            title=f"Zrušený {self.marker}",
            canceled=True,
            requires_verification=False,
        )
        self.assertEqual(overdue.computed_status, TASK_STATUS_ACTIVE)
        self.assertEqual(waiting.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertEqual(done.computed_status, TASK_STATUS_CLOSED)
        self.assertEqual(canceled.computed_status, TASK_STATUS_CANCELED)

        drafts = [
            _draft(status=FINDING_STATUS_VYPORADANO, task_id=overdue.id),
            _draft(status=FINDING_STATUS_VYPORADANO, task_id=waiting.id),
            _draft(status=FINDING_STATUS_VYPORADANO, task_id=done.id),
            _draft(status=FINDING_STATUS_VYPORADANO, task_id=canceled.id),
            _draft(status=FINDING_STATUS_VYPORADANO, task_id=9_001_001),
        ]
        before_tasks = _count("tasks")
        before_findings = _count("findings")
        with (
            patch.object(task_service, "get_tasks_by_ids", wraps=task_service.get_tasks_by_ids) as spy,
            patch.object(Session, "commit") as commit,
            patch.object(Session, "flush") as flush,
        ):
            result = state_supervision_closure_readiness(drafts)
            spy.assert_called_once()
            commit.assert_not_called()
            flush.assert_not_called()
        self.assertEqual(result.active_tasks_count, 2)
        self.assertEqual(result.missing_tasks_count, 1)
        self.assertEqual(_count("tasks"), before_tasks)
        self.assertEqual(_count("findings"), before_findings)
        self.assertEqual(
            task_service.get_task_by_id(overdue.id).computed_status,
            TASK_STATUS_ACTIVE,
        )

    def test_05_warning_text_hides_zero_rows(self) -> None:
        text = format_closure_warning_text(
            StateSupervisionClosureReadiness(open_findings_count=2)
        )
        self.assertIn(CLOSURE_WARNING_INTRO, text)
        self.assertIn(f"– {CLOSURE_WARNING_OPEN_FINDINGS}: 2", text)
        self.assertNotIn(CLOSURE_WARNING_ACTIVE_TASKS, text)
        self.assertNotIn(CLOSURE_WARNING_MISSING_TASKS, text)
        self.assertIn(CLOSURE_WARNING_FOOTER, text)

        tasks_only = format_closure_warning_text(
            StateSupervisionClosureReadiness(active_tasks_count=1, missing_tasks_count=3)
        )
        self.assertNotIn(CLOSURE_WARNING_OPEN_FINDINGS, tasks_only)
        self.assertIn(f"– {CLOSURE_WARNING_ACTIVE_TASKS}: 1", tasks_only)
        self.assertIn(f"– {CLOSURE_WARNING_MISSING_TASKS}: 3", tasks_only)

    def test_06_confirm_dialog_buttons_default_cancel(self) -> None:
        readiness = StateSupervisionClosureReadiness(open_findings_count=1)
        captured: dict[str, object] = {}

        def fake_exec(self):
            captured["labels"] = [btn.text() for btn in self.buttons()]
            captured["default"] = self.defaultButton().text()
            captured["escape"] = self.escapeButton().text()
            captured["icon"] = self.icon()
            captured["body"] = self.text()
            self.reject()
            return 0

        with patch.object(QMessageBox, "exec", fake_exec):
            self.assertFalse(confirm_supervision_closure(None, readiness))
        self.assertIn(ACTION_CONFIRM_CLOSE_SUPERVISION, captured["labels"])
        self.assertIn(EDITOR_CANCEL_LABEL, captured["labels"])
        self.assertNotIn("Ano", captured["labels"])
        self.assertNotIn("Ne", captured["labels"])
        self.assertEqual(captured["default"], EDITOR_CANCEL_LABEL)
        self.assertEqual(captured["escape"], EDITOR_CANCEL_LABEL)
        self.assertEqual(captured["icon"], QMessageBox.Icon.Warning)
        self.assertIn(CLOSURE_WARNING_OPEN_FINDINGS, str(captured["body"]))

        real_exec = QMessageBox.exec

        def click_close(self):
            for btn in self.buttons():
                if btn.text() == ACTION_CONFIRM_CLOSE_SUPERVISION:
                    QTimer.singleShot(0, btn.click)
                    return real_exec(self)
            raise AssertionError("chybí tlačítko Uzavřít kontrolu")

        with patch.object(QMessageBox, "exec", click_close):
            self.assertTrue(confirm_supervision_closure(None, readiness))

    def test_07_transition_open_finding_shows_dialog(self) -> None:
        parent = self._supervision()
        self._ss_finding(parent.id, description="Otevřené")
        dialog = self._open_editor(parent.id)
        self._prepare_close(dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertFalse(self._save(dialog))
            confirm.assert_called_once()
            self.assertEqual(confirm.call_args.args[1].open_findings_count, 1)
        self.assertEqual(
            state_supervision_service.get_supervision(parent.id).status,
            STATUS_ANNOUNCED,
        )
        dialog.close()

    def test_08_transition_active_and_missing_task(self) -> None:
        parent = self._supervision()
        task = task_service.create_task(
            title=f"Aktivní {self.marker}",
            requires_verification=False,
        )
        self._ss_finding(
            parent.id,
            description="S úkolem",
            status=FINDING_STATUS_VYPORADANO,
            task_id=task.id,
        )
        dialog = self._open_editor(parent.id)
        self._prepare_close(dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertFalse(self._save(dialog))
            confirm.assert_called_once()
            self.assertEqual(confirm.call_args.args[1].active_tasks_count, 1)
        dialog.close()

        missing_parent = self._supervision(authority_name=f"Chybějící {self.marker}")
        self._ss_finding(
            missing_parent.id,
            description="Bez úkolu v DB",
            status=FINDING_STATUS_VYPORADANO,
            task_id=8_888_001,
        )
        missing_dialog = self._open_editor(missing_parent.id)
        self._prepare_close(missing_dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertFalse(self._save(missing_dialog))
            confirm.assert_called_once()
            self.assertEqual(confirm.call_args.args[1].missing_tasks_count, 1)
        missing_dialog.close()

    def test_09_no_dialog_when_clean_or_already_closed_or_cancelled(self) -> None:
        empty = self._supervision(authority_name=f"Bez zjištění {self.marker}")
        empty_dialog = self._open_editor(empty.id)
        self._prepare_close(empty_dialog)
        with patch(_CONFIRM) as confirm:
            self.assertTrue(self._save(empty_dialog))
            confirm.assert_not_called()
        self.assertEqual(
            state_supervision_service.get_supervision(empty.id).status,
            STATUS_CLOSED,
        )
        empty_dialog.close()

        clean = self._supervision()
        self._ss_finding(clean.id, description="Bez problému po vypořádání")
        dialog = self._open_editor(clean.id)
        dialog._findings_drafts[0] = replace(
            dialog._findings_drafts[0],
            status=FINDING_STATUS_VYPORADANO,
        )
        self._prepare_close(dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertTrue(self._save(dialog))
            confirm.assert_not_called()
        self.assertEqual(
            state_supervision_service.get_supervision(clean.id).status,
            STATUS_CLOSED,
        )
        dialog.close()

        closed = self._supervision(
            status=STATUS_CLOSED,
            authority_name=f"Už uzavřená {self.marker}",
            closed_at=_CLOSED_AT,
        )
        self._ss_finding(closed.id, description="Zůstává otevřené")
        opened = self._open_editor(closed.id)
        with patch(_CONFIRM) as confirm:
            opened.tabs.setCurrentIndex(opened._conclusion_tab_index)
            opened.tabs.setCurrentIndex(opened._course_tab_index)
            confirm.assert_not_called()
        opened.subject_edit.setPlainText("Jen poznámka")
        opened._editor.refresh_dirty()
        with patch(_CONFIRM) as confirm:
            self.assertTrue(self._save(opened))
            confirm.assert_not_called()
        self.assertEqual(
            state_supervision_service.get_supervision(closed.id).status,
            STATUS_CLOSED,
        )
        opened.close()

        cancelled = self._supervision()
        self._ss_finding(cancelled.id, description="Při zrušení")
        cancel_dialog = self._open_editor(cancelled.id)
        cancel_dialog.status_combo.setCurrentIndex(
            cancel_dialog.status_combo.findData(STATUS_CANCELLED)
        )
        with patch(_CONFIRM) as confirm:
            self.assertTrue(self._save(cancel_dialog))
            confirm.assert_not_called()
        self.assertEqual(
            state_supervision_service.get_supervision(cancelled.id).status,
            STATUS_CANCELLED,
        )
        cancel_dialog.close()

        fresh = StateSupervisionEditorDialog()
        with patch(_CONFIRM) as confirm:
            fresh.tabs.setCurrentIndex(fresh._course_tab_index)
            confirm.assert_not_called()
        fresh.close()

    def test_10_closed_without_closed_at_validates_before_warning(self) -> None:
        parent = self._supervision()
        self._ss_finding(parent.id, description="Bez data uzavření")
        dialog = self._open_editor(parent.id)
        dialog.status_combo.setCurrentIndex(dialog.status_combo.findData(STATUS_CLOSED))
        with (
            patch(_CONFIRM) as confirm,
            patch.object(QMessageBox, "warning") as warning,
        ):
            self.assertFalse(self._save(dialog))
            confirm.assert_not_called()
            self.assertIn(CLOSED_AT_REQUIRED_MESSAGE, warning.call_args.args)
        self.assertEqual(dialog.tabs.currentIndex(), dialog._conclusion_tab_index)
        dialog.close()

    def test_11_working_drafts_not_db_snapshot(self) -> None:
        parent = self._supervision()
        stored = self._ss_finding(
            parent.id,
            description="V DB otevřené",
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = self._open_editor(parent.id)
        dialog._findings_drafts[0] = replace(
            dialog._findings_drafts[0],
            status=FINDING_STATUS_VYPORADANO,
        )
        extra = _draft(
            description="Nové otevřené v editoru",
            status=FINDING_STATUS_OTEVRENE,
            client_key=f"new-{self.marker}",
        )
        dialog._findings_drafts.append(extra)
        dialog._refresh_findings_table()
        self._prepare_close(dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertFalse(self._save(dialog))
            readiness = confirm.call_args.args[1]
            self.assertEqual(readiness.open_findings_count, 1)
        reloaded = finding_service.get_by_id(stored.id)
        self.assertEqual(reloaded.status, FINDING_STATUS_OTEVRENE)
        dialog.close()

    def test_12_cancel_keeps_working_state_focuses_course(self) -> None:
        parent = self._supervision()
        task = task_service.create_task(
            title=f"Zůstane aktivní {self.marker}",
            requires_verification=False,
        )
        finding = self._ss_finding(
            parent.id,
            description="Zůstane otevřené",
            task_id=task.id,
        )
        before_findings = _count("findings")
        before_tasks = _count("tasks")
        dialog = self._open_editor(parent.id)
        dialog.tabs.setCurrentIndex(dialog._conclusion_tab_index)
        dialog.subject_edit.setPlainText("Pracovní změna")
        self._prepare_close(dialog)
        self.assertTrue(dialog._editor.is_dirty())
        with (
            patch(_CONFIRM, return_value=False),
            patch.object(
                state_supervision_service, "save_supervision_bundle"
            ) as bundle,
            patch("core.services.attachment_service.shutil.copy2") as copy2,
        ):
            self.assertFalse(self._save(dialog))
            bundle.assert_not_called()
            copy2.assert_not_called()
        loaded = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(loaded.status, STATUS_ANNOUNCED)
        self.assertIsNone(loaded.closed_at)
        self.assertEqual(dialog.get_data()["status"], STATUS_CLOSED)
        self.assertEqual(dialog.closed_at_edit.get_datetime(), _CLOSED_AT)
        self.assertEqual(dialog.subject_edit.toPlainText(), "Pracovní změna")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(dialog.tabs.currentIndex(), dialog._course_tab_index)
        self.assertEqual(dialog.tabs.tabText(dialog._course_tab_index), TAB_COURSE)
        self.assertEqual(_count("findings"), before_findings)
        self.assertEqual(_count("tasks"), before_tasks)
        self.assertEqual(finding_service.get_by_id(finding.id).status, FINDING_STATUS_OTEVRENE)
        self.assertEqual(
            task_service.get_task_by_id(task.id).computed_status,
            TASK_STATUS_ACTIVE,
        )
        dialog.close()

    def test_13_confirm_saves_bundle_keeps_open_items(self) -> None:
        parent = self._supervision()
        task = task_service.create_task(
            title=f"Po uzavření {self.marker}",
            due_date=date.today(),
            requires_verification=False,
        )
        finding = self._ss_finding(
            parent.id,
            description="Zůstane otevřené po uzavření",
            task_id=task.id,
        )
        dialog = self._open_editor(parent.id)
        self._prepare_close(dialog)
        with patch(_CONFIRM, return_value=True) as confirm:
            self.assertTrue(self._save(dialog))
            confirm.assert_called_once()
        loaded = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(loaded.status, STATUS_CLOSED)
        self.assertEqual(loaded.closed_at, _CLOSED_AT)
        stored = finding_service.get_by_id(finding.id)
        self.assertEqual(stored.status, FINDING_STATUS_OTEVRENE)
        self.assertEqual(stored.task_id, task.id)
        self.assertEqual(
            task_service.get_task_by_id(task.id).computed_status,
            TASK_STATUS_ACTIVE,
        )
        attention = get_attention_items()
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
                for item in attention
            )
        )
        self.assertFalse(dialog._editor.is_dirty())
        dialog.subject_edit.setPlainText("Úprava už uzavřené")
        with patch(_CONFIRM) as confirm_again:
            self.assertTrue(self._save(dialog))
            confirm_again.assert_not_called()
        dialog.close()

        reopened = self._open_editor(parent.id)
        reopened.status_combo.setCurrentIndex(
            reopened.status_combo.findData(STATUS_IN_PROGRESS)
        )
        with patch(_CONFIRM) as confirm:
            self.assertTrue(self._save(reopened))
            confirm.assert_not_called()
        self.assertEqual(
            finding_service.get_by_id(finding.id).status,
            FINDING_STATUS_OTEVRENE,
        )
        self._prepare_close(reopened)
        with patch(_CONFIRM, return_value=True) as confirm:
            self.assertTrue(self._save(reopened))
            confirm.assert_called_once()
        reopened.close()

    def test_14_bundle_error_asks_again_next_save(self) -> None:
        parent = self._supervision()
        self._ss_finding(parent.id, description="Po chybě znovu")
        dialog = self._open_editor(parent.id)
        self._prepare_close(dialog)
        with (
            patch(_CONFIRM, return_value=True) as confirm,
            patch.object(
                state_supervision_service,
                "save_supervision_bundle",
                side_effect=StateSupervisionError("Simulovaná chyba"),
            ),
            patch.object(QMessageBox, "warning"),
        ):
            self.assertFalse(self._save(dialog))
            confirm.assert_called_once()
        self.assertEqual(
            state_supervision_service.get_supervision(parent.id).status,
            STATUS_ANNOUNCED,
        )
        self.assertEqual(dialog.get_data()["status"], STATUS_CLOSED)
        self.assertTrue(dialog._editor.is_dirty())
        with patch(_CONFIRM, return_value=True) as confirm:
            self.assertTrue(self._save(dialog))
            confirm.assert_called_once()
        self.assertEqual(
            state_supervision_service.get_supervision(parent.id).status,
            STATUS_CLOSED,
        )
        dialog.close()

    def test_15_all_three_save_paths(self) -> None:
        parent = self._supervision()
        self._ss_finding(parent.id, description="Uložit")
        dialog = self._open_editor(parent.id)
        self._prepare_close(dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertFalse(self._save(dialog))
            confirm.assert_called_once()
        with patch(_CONFIRM, return_value=True):
            self.assertTrue(self._save(dialog))
        self.assertEqual(dialog.result(), 0)
        dialog.close()

        parent2 = self._supervision(authority_name=f"Zavřít {self.marker}")
        self._ss_finding(parent2.id, description="Uložit a zavřít")
        dialog2 = self._open_editor(parent2.id)
        self._prepare_close(dialog2)
        with (
            patch(_CONFIRM, return_value=False),
            patch.object(dialog2, "accept") as accept,
        ):
            dialog2._save_and_close()
            accept.assert_not_called()
        self.assertEqual(
            state_supervision_service.get_supervision(parent2.id).status,
            STATUS_ANNOUNCED,
        )
        with (
            patch(_CONFIRM, return_value=True),
            patch.object(dialog2, "accept") as accept,
        ):
            dialog2._save_and_close()
            accept.assert_called_once()
        self.assertEqual(
            state_supervision_service.get_supervision(parent2.id).status,
            STATUS_CLOSED,
        )
        dialog2.close()

        parent3 = self._supervision(authority_name=f"Prompt {self.marker}")
        self._ss_finding(parent3.id, description="Zavřít pak Uložit")
        dialog3 = self._open_editor(parent3.id)
        self._prepare_close(dialog3)
        with (
            patch(
                "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
                return_value="save",
            ),
            patch(_CONFIRM, return_value=False),
        ):
            self.assertFalse(dialog3._editor.request_close())
        self.assertEqual(
            state_supervision_service.get_supervision(parent3.id).status,
            STATUS_ANNOUNCED,
        )
        self.assertTrue(dialog3._editor.is_dirty())
        with (
            patch(
                "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
                return_value="save",
            ),
            patch(_CONFIRM, return_value=True),
        ):
            self.assertTrue(dialog3._editor.request_close())
        self.assertEqual(
            state_supervision_service.get_supervision(parent3.id).status,
            STATUS_CLOSED,
        )
        dialog3.close()

    def test_16_history_source_and_regressions(self) -> None:
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        self.assertLess(
            persist.find("_validation_message"),
            persist.find("_confirm_closure_if_needed"),
        )
        self.assertLess(
            persist.find("_confirm_closure_if_needed"),
            persist.find("save_supervision_bundle"),
        )
        self.assertIn("findings=self._findings_drafts_for_save()", persist)
        self.assertNotIn("FINDING_STATUS_VYPORADANO", persist)
        signature = inspect.signature(StateSupervisionService.save_supervision_bundle)
        self.assertIn("findings", signature.parameters)

        probe = StateSupervisionEditorDialog()
        self.assertEqual(probe.tabs.count(), 5)
        self.assertEqual(
            [probe.tabs.tabText(i) for i in range(probe.tabs.count())],
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        self.assertIsInstance(probe._editor, EditorDialogController)
        probe.close()

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)

        closed = self._supervision(
            status=STATUS_CLOSED,
            authority_name=f"Navigace {self.marker}",
            closed_at=_CLOSED_AT,
        )
        finding = self._ss_finding(closed.id, description="Zdroj uzavřené")
        opened: list[int | None] = []

        class FakeDialog:
            def __init__(self, parent=None, *, supervision_id=None):
                opened.append(supervision_id)
                self.saved = False
                self.supervision_id = supervision_id

        host = MagicMock()
        host._page_widgets = {"agenda": page}
        host._show = MagicMock()
        source_navigator.configure(host)
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
            self.assertTrue(source_navigator.open_finding(finding.id))
        self.assertEqual(opened[-1], closed.id)
        page.close()


if __name__ == "__main__":
    unittest.main()
