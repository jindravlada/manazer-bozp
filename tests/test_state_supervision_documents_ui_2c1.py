"""STATE-SUPERVISION-DOCUMENTS-UI-2C1: evidence požadovaných dokladů."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QMessageBox, QTabWidget
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-docs-ui-2c1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import EditorDialogController
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_ADD,
        ACTION_EDIT,
        ACTION_MOVE_DOWN,
        ACTION_MOVE_UP,
        ACTION_REMOVE,
        DOCUMENT_COLUMN_HEADERS,
        EMPTY_VALUE,
        GROUP_REQUIRED_DOCUMENTS,
        RESPONSIBLE_SOURCE_PERSON,
        RESPONSIBLE_SOURCE_THP_WORKER,
        TAB_ANNOUNCEMENT,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_required_document_dialog import (
        StateSupervisionRequiredDocumentDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab


def _count(table: str) -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _active_document_titles(supervision_id: int) -> list[str]:
    rows = state_supervision_required_document_service.list_documents(supervision_id)
    return [str(row.title) for row in rows]


class StateSupervisionDocumentsUi2c1TestCase(unittest.TestCase):
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
        self.person = person_service.create_person(
            first_name="Jana",
            last_name=f"Osoba-{self.marker}",
        )
        self.worker = settings_service.save_worker(
            first_name="Petr",
            last_name=f"THP-{self.marker}",
        )

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _add_working(
        self,
        dialog: StateSupervisionEditorDialog,
        **fields,
    ) -> StateSupervisionRequiredDocumentDraft:
        payload = {"title": f"Doklad {self.marker}"}
        payload.update(fields)
        draft = StateSupervisionRequiredDocumentDraft(**payload)
        dialog._document_drafts.append(draft)
        dialog._refresh_documents_table(select_key=draft.client_key)
        dialog._editor.refresh_dirty()
        return draft

    def test_01_section_on_second_tab_six_columns_and_buttons(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.tabs.count(), 5)
        self.assertEqual(dialog.tabs.tabText(0), TAB_ANNOUNCEMENT)
        self.assertEqual(dialog.tabs.tabText(1), TAB_SUBJECT_PREPARATION)
        groups = [box.title() for box in dialog.findChildren(QGroupBox)]
        self.assertIn(GROUP_REQUIRED_DOCUMENTS, groups)
        self.assertEqual(
            [dialog.documents_table.horizontalHeaderItem(i).text() for i in range(6)],
            DOCUMENT_COLUMN_HEADERS,
        )
        self.assertEqual(dialog.documents_table.columnCount(), 6)
        self.assertEqual(dialog.documents_table.textElideMode(), Qt.TextElideMode.ElideRight)
        self.assertFalse(dialog.documents_table.isSortingEnabled())
        self.assertEqual(dialog.add_document_btn.text(), ACTION_ADD)
        self.assertEqual(dialog.edit_document_btn.text(), ACTION_EDIT)
        self.assertEqual(dialog.remove_document_btn.text(), ACTION_REMOVE)
        self.assertEqual(dialog.move_document_up_btn.text(), ACTION_MOVE_UP)
        self.assertEqual(dialog.move_document_down_btn.text(), ACTION_MOVE_DOWN)
        self.assertTrue(dialog.add_document_btn.isEnabled())
        self.assertFalse(dialog.edit_document_btn.isEnabled())
        self.assertFalse(dialog.remove_document_btn.isEnabled())
        self.assertFalse(dialog.move_document_up_btn.isEnabled())
        self.assertFalse(dialog.move_document_down_btn.isEnabled())
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("doubleClicked.connect(self._edit_selected_document)", source)
        dialog.close()

    def test_02_add_edit_cancel_and_noop_confirm(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")

        created = StateSupervisionRequiredDocumentDraft(title="BL chemie")
        with patch(
            "moduly.statni_dozor.ui.state_supervision_required_document_dialog."
            "exec_required_document_dialog",
            return_value=created,
        ):
            dialog._add_document()
        self.assertEqual(len(dialog._active_documents()), 1)
        self.assertIsNone(dialog._active_documents()[0].id)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog.edit_document_btn.isEnabled())

        with patch(
            "moduly.statni_dozor.ui.state_supervision_required_document_dialog."
            "exec_required_document_dialog",
            return_value=None,
        ):
            dialog._add_document()
        self.assertEqual(len(dialog._active_documents()), 1)

        current = dialog._active_documents()[0]
        with patch(
            "moduly.statni_dozor.ui.state_supervision_required_document_dialog."
            "exec_required_document_dialog",
            return_value=replace(current),
        ):
            dialog._edit_selected_document()
        self.assertEqual(dialog._active_documents()[0].title, "BL chemie")
        self.assertTrue(dialog._editor.is_dirty())

        dialog._editor.capture_baseline()
        self.assertFalse(dialog._editor.is_dirty())
        with patch(
            "moduly.statni_dozor.ui.state_supervision_required_document_dialog."
            "exec_required_document_dialog",
            return_value=replace(dialog._active_documents()[0]),
        ):
            dialog._edit_selected_document()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

    def test_03_remove_new_vs_existing_soft_delete_and_move(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"KHS {self.marker}"
        )
        existing = state_supervision_required_document_service.create_document(
            record.id, title="Existující"
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self._add_working(dialog, title="Nový pracovní")
        self.assertEqual(len(dialog._active_documents()), 2)

        dialog._select_document_key(dialog._active_documents()[1].client_key)
        dialog._remove_selected_document()
        self.assertEqual([row.title for row in dialog._active_documents()], ["Existující"])
        self.assertEqual(
            len(state_supervision_required_document_service.list_documents(record.id)),
            1,
        )

        dialog._select_document_key(dialog._active_documents()[0].client_key)
        dialog._remove_selected_document()
        self.assertEqual(dialog._active_documents(), [])
        kept = [
            item for item in dialog._document_drafts if item.id == existing.id
        ]
        self.assertEqual(len(kept), 1)
        self.assertFalse(kept[0].active)
        self.assertEqual(
            len(
                state_supervision_required_document_service.list_documents(
                    record.id, include_inactive=True
                )
            ),
            1,
        )
        dialog.close()

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Move {self.marker}")
        self._add_working(dialog, title="A-první")
        second = self._add_working(dialog, title="B-druhý")
        dialog._select_document_key(second.client_key)
        dialog._move_selected_document(-1)
        self.assertEqual(
            [row.title for row in dialog._active_documents()],
            ["B-druhý", "A-první"],
        )
        self.assertTrue(dialog._editor.is_dirty())
        dialog.documents_table.clearSelection()
        dialog.documents_table.setCurrentCell(-1, -1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

    def test_04_person_thp_snapshot_and_nullable_datetime(self) -> None:
        due = datetime(2026, 4, 1, 9, 30)
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        self._add_working(
            dialog,
            title="Prezenční listina",
            responsible_source_type=RESPONSIBLE_SOURCE_PERSON,
            responsible_source_id=self.person.id,
            responsible_name_snapshot="Jana historická",
            due_at=due,
        )
        self._add_working(
            dialog,
            title="Oprávnění THP",
            responsible_source_type=RESPONSIBLE_SOURCE_THP_WORKER,
            responsible_source_id=self.worker.id,
            responsible_name_snapshot="Petr THP",
        )
        self._add_working(dialog, title="Bez osoby a termínu")
        self.assertTrue(self._save(dialog))
        loaded = StateSupervisionEditorDialog(supervision_id=dialog.supervision_id)
        titles = [row.title for row in loaded._active_documents()]
        self.assertEqual(
            titles,
            ["Prezenční listina", "Oprávnění THP", "Bez osoby a termínu"],
        )
        first = loaded._active_documents()[0]
        self.assertEqual(first.responsible_source_type, RESPONSIBLE_SOURCE_PERSON)
        self.assertIn("Jana", first.responsible_name_snapshot or "")
        self.assertEqual(first.due_at, due)
        second = loaded._active_documents()[1]
        self.assertEqual(second.responsible_source_type, RESPONSIBLE_SOURCE_THP_WORKER)
        self.assertIn("Petr", second.responsible_name_snapshot or "")
        self.assertIsNone(loaded._active_documents()[2].responsible_source_type)
        self.assertIsNone(loaded._active_documents()[2].due_at)
        self.assertEqual(
            loaded.documents_table.item(2, 1).text(),
            EMPTY_VALUE,
        )
        loaded.close()
        dialog.close()

        missing = StateSupervisionRequiredDocumentDialog(
            draft=StateSupervisionRequiredDocumentDraft(
                title="Historie",
                responsible_source_type=RESPONSIBLE_SOURCE_PERSON,
                responsible_source_id=9_999_999,
                responsible_name_snapshot="Ing. Zmizelá",
            )
        )
        self.assertEqual(missing.person_selector.currentText(), "Ing. Zmizelá")
        missing.close()

    def test_05_dirty_add_edit_remove_order_and_revert(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"DÚ {self.marker}"
        )
        state_supervision_required_document_service.create_document(
            record.id, title="Původní A"
        )
        state_supervision_required_document_service.create_document(
            record.id, title="Původní B"
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        baseline = dialog.get_snapshot()

        added = self._add_working(dialog, title="Nový")
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog._document_drafts = [
            item for item in dialog._document_drafts if item.client_key != added.client_key
        ]
        dialog._refresh_documents_table()
        dialog._editor.refresh_dirty()
        self.assertEqual(dialog.get_snapshot(), baseline)
        self.assertFalse(dialog._editor.save_button.isEnabled())

        current = dialog._active_documents()[0]
        current.title = "Původní A upraveno"
        dialog._refresh_documents_table()
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        current.title = "Původní A"
        dialog._refresh_documents_table()
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        dialog._select_document_key(dialog._active_documents()[1].client_key)
        dialog._move_selected_document(-1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog._select_document_key(dialog._active_documents()[0].client_key)
        dialog._move_selected_document(1)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.setCurrentIndex(0)
        dialog.documents_table.selectRow(0)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

    def test_06_persist_bundle_ids_order_and_second_save(self) -> None:
        before = _count("state_supervisions")
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OBÚ {self.marker}")
        self._add_working(dialog, title="První")
        self._add_working(dialog, title="Druhý")
        self.assertTrue(self._save(dialog))
        self.assertEqual(_count("state_supervisions"), before + 1)
        self.assertIsNotNone(dialog.supervision_id)
        self.assertTrue(all(item.id is not None for item in dialog._active_documents()))
        self.assertEqual(_active_document_titles(dialog.supervision_id), ["První", "Druhý"])
        self.assertFalse(dialog._editor.is_dirty())

        dialog._active_documents()[0].title = "První upraveno"
        self._add_working(dialog, title="Třetí")
        self.assertTrue(self._save(dialog))
        titles = _active_document_titles(dialog.supervision_id)
        self.assertEqual(titles, ["První upraveno", "Druhý", "Třetí"])
        self.assertEqual(len(titles), 3)

        dialog._select_document_key(dialog._active_documents()[1].client_key)
        dialog._remove_selected_document()
        self.assertTrue(self._save(dialog))
        self.assertEqual(
            _active_document_titles(dialog.supervision_id),
            ["První upraveno", "Třetí"],
        )
        history = state_supervision_required_document_service.list_documents(
            dialog.supervision_id, include_inactive=True
        )
        self.assertEqual(len(history), 3)
        self.assertEqual(sum(1 for row in history if row.active), 2)
        reopened = StateSupervisionEditorDialog(supervision_id=dialog.supervision_id)
        self.assertEqual(
            [row.title for row in reopened._active_documents()],
            ["První upraveno", "Třetí"],
        )
        reopened.close()
        dialog.close()

    def test_07_atomic_rollback_and_single_commit(self) -> None:
        before_s = _count("state_supervisions")
        before_d = _count("state_supervision_required_documents")
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_with_documents(
                supervision_id=None,
                fields={"authority_name": "   "},
                documents=[StateSupervisionRequiredDocumentDraft(title="A")],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)

        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_with_documents(
                supervision_id=None,
                fields={"authority_name": f"OIP {self.marker}"},
                documents=[
                    StateSupervisionRequiredDocumentDraft(title="Platný"),
                    StateSupervisionRequiredDocumentDraft(title="  "),
                ],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)

        existing = state_supervision_service.create_supervision(
            authority_name=f"Keep {self.marker}"
        )
        doc = state_supervision_required_document_service.create_document(
            existing.id, title="Původní"
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_with_documents(
                supervision_id=existing.id,
                fields={"authority_name": f"Změna {self.marker}"},
                documents=[
                    StateSupervisionRequiredDocumentDraft(
                        id=doc.id, title="Nemá se uložit"
                    ),
                    StateSupervisionRequiredDocumentDraft(title=""),
                ],
            )
        reloaded = state_supervision_service.get_supervision(existing.id)
        self.assertEqual(reloaded.authority_name, f"Keep {self.marker}")
        self.assertEqual(_active_document_titles(existing.id), ["Původní"])

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Rollback {self.marker}")
        self._add_working(dialog, title="Pracovní")
        with patch.object(
            state_supervision_required_document_service,
            "save_document_batch",
            side_effect=StateSupervisionError("umělá chyba dokladu"),
        ):
            with patch.object(QMessageBox, "warning"):
                self.assertFalse(self._save(dialog))
        self.assertIsNone(dialog.supervision_id)
        self.assertIsNone(dialog._active_documents()[0].id)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

        source = inspect.getsource(
            StateSupervisionService.save_supervision_bundle
        )
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)
        repo_source = inspect.getsource(
            type(state_supervision_required_document_service.repository).save_all
        )
        self.assertIn("if owns:", repo_source)

        commits = []
        original = Session.commit

        def _spy(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with patch.object(Session, "commit", _spy):
            state_supervision_service.save_supervision_with_documents(
                supervision_id=None,
                fields={"authority_name": f"Commit {self.marker}"},
                documents=[
                    StateSupervisionRequiredDocumentDraft(title="A"),
                    StateSupervisionRequiredDocumentDraft(title="B"),
                ],
            )
        self.assertEqual(len(commits), 1)

    def test_08_no_write_on_open_and_agenda_four_tabs(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Open {self.marker}"
        )
        state_supervision_required_document_service.create_document(
            record.id, title="Načíst"
        )
        before_s = _count("state_supervisions")
        before_d = _count("state_supervision_required_documents")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertIsInstance(dialog._editor, EditorDialogController)
        dialog.tabs.setCurrentIndex(1)
        dialog.close()
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        self.assertIsInstance(page.state_supervision_tab, StateSupervisionTab)

    def test_09_subdialog_fields_and_window_modal(self) -> None:
        sub = StateSupervisionRequiredDocumentDialog(is_new=True)
        self.assertEqual(sub.windowModality(), Qt.WindowModality.WindowModal)
        self.assertTrue(sub.title_edit)
        self.assertTrue(sub.person_selector)
        self.assertTrue(sub.due_at_edit)
        self.assertTrue(sub.prepared_at_edit)
        self.assertTrue(sub.submitted_at_edit)
        self.assertTrue(sub.note_edit)
        sub.title_edit.setText("  ")
        with patch.object(QMessageBox, "warning") as warning:
            sub._on_save()
            warning.assert_called()
        self.assertIsNone(sub.result_draft)
        sub.title_edit.setText("Protokol")
        sub._on_save()
        self.assertEqual(sub.result_draft.title, "Protokol")
        self.assertIsNone(sub.result_draft.responsible_source_type)
        sub.close()

        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("save_supervision_bundle", source)
        self.assertNotIn("DELETE FROM", source)
        self.assertEqual(source.count("create_supervision("), 0)


if __name__ == "__main__":
    unittest.main()
