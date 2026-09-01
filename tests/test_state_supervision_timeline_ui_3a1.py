"""STATE-SUPERVISION-TIMELINE-UI-3A1: evidence průběhu kontroly."""

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
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTabWidget
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-timeline-ui-3a1-"))

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
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_ADD,
        ACTION_EDIT,
        ACTION_MOVE_DOWN,
        ACTION_MOVE_UP,
        ACTION_REMOVE,
        EMPTY_TIMELINE,
        EMPTY_VALUE,
        TAB_ANNOUNCEMENT,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
        TIMELINE_COLUMN_HEADERS,
        TIMELINE_HINT,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        KEEP_EXISTING,
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
        state_supervision_timeline_item_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab
    from moduly.statni_dozor.ui.state_supervision_timeline_item_dialog import (
        StateSupervisionTimelineItemDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_table import (
        format_supervision_datetime,
    )


def _count(table: str) -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _active_titles(supervision_id: int) -> list[str]:
    rows = state_supervision_timeline_item_service.list_timeline_items(supervision_id)
    return [str(row.title) for row in rows]


def _active_document_titles(supervision_id: int) -> list[str]:
    rows = state_supervision_required_document_service.list_documents(supervision_id)
    return [str(row.title) for row in rows]


class StateSupervisionTimelineUi3a1TestCase(unittest.TestCase):
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

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _add_working(
        self,
        dialog: StateSupervisionEditorDialog,
        **fields,
    ) -> StateSupervisionTimelineItemDraft:
        payload = {"title": f"Úkon {self.marker}"}
        payload.update(fields)
        draft = StateSupervisionTimelineItemDraft(**payload)
        dialog._timeline_drafts.append(draft)
        dialog._refresh_timeline_table(select_key=draft.client_key)
        dialog._editor.refresh_dirty()
        return draft

    def test_01_three_tabs_four_columns_and_buttons(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.tabs.count(), 4)
        self.assertEqual(dialog.tabs.tabText(0), TAB_ANNOUNCEMENT)
        self.assertEqual(dialog.tabs.tabText(1), TAB_SUBJECT_PREPARATION)
        self.assertEqual(dialog.tabs.tabText(2), TAB_COURSE)
        self.assertEqual(dialog.tabs.tabText(3), TAB_CONCLUSION)
        self.assertEqual(dialog.timeline_hint_label.text(), TIMELINE_HINT)
        self.assertEqual(dialog.timeline_empty_label.text(), EMPTY_TIMELINE)
        self.assertFalse(dialog.timeline_empty_label.isHidden())
        self.assertEqual(
            [dialog.timeline_table.horizontalHeaderItem(i).text() for i in range(4)],
            TIMELINE_COLUMN_HEADERS,
        )
        self.assertEqual(dialog.timeline_table.columnCount(), 4)
        self.assertEqual(dialog.timeline_table.textElideMode(), Qt.TextElideMode.ElideRight)
        self.assertFalse(dialog.timeline_table.isSortingEnabled())
        self.assertEqual(dialog.add_timeline_btn.text(), ACTION_ADD)
        self.assertEqual(dialog.edit_timeline_btn.text(), ACTION_EDIT)
        self.assertEqual(dialog.remove_timeline_btn.text(), ACTION_REMOVE)
        self.assertEqual(dialog.move_timeline_up_btn.text(), ACTION_MOVE_UP)
        self.assertEqual(dialog.move_timeline_down_btn.text(), ACTION_MOVE_DOWN)
        self.assertTrue(dialog.add_timeline_btn.isEnabled())
        self.assertFalse(dialog.edit_timeline_btn.isEnabled())
        self.assertFalse(dialog.remove_timeline_btn.isEnabled())
        self.assertFalse(dialog.move_timeline_up_btn.isEnabled())
        self.assertFalse(dialog.move_timeline_down_btn.isEnabled())
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("doubleClicked.connect(self._edit_selected_timeline_item)", source)
        self.assertNotIn("PKZ", source)
        self.assertNotIn("Závada", source)
        dialog.close()

    def test_02_add_edit_cancel_noop_and_empty_state(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")

        created = StateSupervisionTimelineItemDraft(title="Zahájení kontroly")
        with patch(
            "moduly.statni_dozor.ui.state_supervision_timeline_item_dialog."
            "exec_timeline_item_dialog",
            return_value=created,
        ):
            dialog._add_timeline_item()
        self.assertEqual(len(dialog._active_timeline_items()), 1)
        self.assertIsNone(dialog._active_timeline_items()[0].id)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog.timeline_empty_label.isHidden())
        self.assertEqual(_count("state_supervision_timeline_items"), 0)
        self.assertTrue(dialog.edit_timeline_btn.isEnabled())

        with patch(
            "moduly.statni_dozor.ui.state_supervision_timeline_item_dialog."
            "exec_timeline_item_dialog",
            return_value=None,
        ):
            dialog._add_timeline_item()
        self.assertEqual(len(dialog._active_timeline_items()), 1)

        current = dialog._active_timeline_items()[0]
        with patch(
            "moduly.statni_dozor.ui.state_supervision_timeline_item_dialog."
            "exec_timeline_item_dialog",
            return_value=replace(current),
        ):
            dialog._edit_selected_timeline_item()
        self.assertEqual(dialog._active_timeline_items()[0].title, "Zahájení kontroly")
        self.assertTrue(dialog._editor.is_dirty())

        dialog._editor.capture_baseline()
        self.assertFalse(dialog._editor.is_dirty())
        with patch(
            "moduly.statni_dozor.ui.state_supervision_timeline_item_dialog."
            "exec_timeline_item_dialog",
            return_value=replace(dialog._active_timeline_items()[0]),
        ):
            dialog._edit_selected_timeline_item()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

    def test_03_remove_new_vs_existing_soft_delete_and_move(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"KHS {self.marker}"
        )
        existing = state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Existující"
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self._add_working(dialog, title="Nový pracovní")
        self.assertEqual(len(dialog._active_timeline_items()), 2)

        dialog._select_timeline_key(dialog._active_timeline_items()[1].client_key)
        dialog._remove_selected_timeline_item()
        self.assertEqual(
            [row.title for row in dialog._active_timeline_items()],
            ["Existující"],
        )
        self.assertEqual(
            len(state_supervision_timeline_item_service.list_timeline_items(record.id)),
            1,
        )

        dialog._select_timeline_key(dialog._active_timeline_items()[0].client_key)
        dialog._remove_selected_timeline_item()
        self.assertEqual(dialog._active_timeline_items(), [])
        kept = [item for item in dialog._timeline_drafts if item.id == existing.id]
        self.assertEqual(len(kept), 1)
        self.assertFalse(kept[0].active)
        self.assertEqual(
            len(
                state_supervision_timeline_item_service.list_timeline_items(
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
        dialog._select_timeline_key(second.client_key)
        dialog._move_selected_timeline_item(-1)
        self.assertEqual(
            [row.title for row in dialog._active_timeline_items()],
            ["B-druhý", "A-první"],
        )
        self.assertTrue(dialog._editor.is_dirty())
        dialog.timeline_table.clearSelection()
        dialog.timeline_table.setCurrentCell(-1, -1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

    def test_04_nullable_datetime_empty_place_czech_notes_tooltip(self) -> None:
        occurred = datetime(2026, 4, 15, 9, 30)
        notes = "Průběh:\nžluťoučký kůň\núpěl ďábelské ódy."
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        self._add_working(
            dialog,
            title="Zahájení kontroly",
            occurred_at=occurred,
            place="Hala A",
            notes=notes,
        )
        self._add_working(
            dialog,
            title="Doplněno zpětně",
            occurred_at=None,
            place="",
            notes="",
        )
        self.assertEqual(
            dialog.timeline_table.item(0, 0).text(),
            format_supervision_datetime(occurred),
        )
        self.assertEqual(dialog.timeline_table.item(1, 0).text(), EMPTY_VALUE)
        self.assertEqual(dialog.timeline_table.item(1, 2).text(), EMPTY_VALUE)
        self.assertEqual(dialog.timeline_table.item(1, 3).text(), EMPTY_VALUE)
        self.assertIn(notes, dialog.timeline_table.item(0, 3).toolTip())
        self.assertEqual(dialog.timeline_table.item(1, 0).toolTip(), "")
        self.assertTrue(self._save(dialog))
        loaded = StateSupervisionEditorDialog(supervision_id=dialog.supervision_id)
        first = loaded._active_timeline_items()[0]
        second = loaded._active_timeline_items()[1]
        self.assertEqual(first.occurred_at, occurred)
        self.assertEqual(first.place, "Hala A")
        self.assertEqual(first.notes, notes)
        self.assertIsNone(second.occurred_at)
        self.assertIsNone(second.place)
        self.assertIsNone(second.notes)
        loaded.close()
        dialog.close()

    def test_05_dirty_add_edit_remove_order_and_revert(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"DÚ {self.marker}"
        )
        state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Původní A"
        )
        state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Původní B"
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        baseline = dialog.get_snapshot()

        added = self._add_working(dialog, title="Nový")
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog._timeline_drafts = [
            item
            for item in dialog._timeline_drafts
            if item.client_key != added.client_key
        ]
        dialog._refresh_timeline_table()
        dialog._editor.refresh_dirty()
        self.assertEqual(dialog.get_snapshot(), baseline)
        self.assertFalse(dialog._editor.save_button.isEnabled())

        current = dialog._active_timeline_items()[0]
        current.title = "Původní A upraveno"
        dialog._refresh_timeline_table()
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        current.title = "Původní A"
        dialog._refresh_timeline_table()
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        dialog._select_timeline_key(dialog._active_timeline_items()[1].client_key)
        dialog._move_selected_timeline_item(-1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog._select_timeline_key(dialog._active_timeline_items()[0].client_key)
        dialog._move_selected_timeline_item(1)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        dialog.tabs.setCurrentIndex(2)
        dialog.tabs.setCurrentIndex(0)
        dialog.timeline_table.selectRow(0)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

    def test_06_persist_bundle_ids_order_and_second_save(self) -> None:
        before = _count("state_supervisions")
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OBÚ {self.marker}")
        dialog._document_drafts.append(
            StateSupervisionRequiredDocumentDraft(title="Doklad A")
        )
        dialog._refresh_documents_table()
        self._add_working(dialog, title="První")
        self._add_working(dialog, title="Druhý")
        self.assertTrue(self._save(dialog))
        self.assertEqual(_count("state_supervisions"), before + 1)
        self.assertIsNotNone(dialog.supervision_id)
        self.assertTrue(
            all(item.id is not None for item in dialog._active_timeline_items())
        )
        self.assertEqual(_active_titles(dialog.supervision_id), ["První", "Druhý"])
        self.assertEqual(_active_document_titles(dialog.supervision_id), ["Doklad A"])
        self.assertFalse(dialog._editor.is_dirty())

        dialog._active_timeline_items()[0].title = "První upraveno"
        self._add_working(dialog, title="Třetí")
        self.assertTrue(self._save(dialog))
        titles = _active_titles(dialog.supervision_id)
        self.assertEqual(titles, ["První upraveno", "Druhý", "Třetí"])

        dialog._select_timeline_key(dialog._active_timeline_items()[1].client_key)
        dialog._remove_selected_timeline_item()
        self.assertTrue(self._save(dialog))
        self.assertEqual(
            _active_titles(dialog.supervision_id),
            ["První upraveno", "Třetí"],
        )
        history = state_supervision_timeline_item_service.list_timeline_items(
            dialog.supervision_id, include_inactive=True
        )
        self.assertEqual(len(history), 3)
        self.assertEqual(sum(1 for row in history if row.active), 2)
        reopened = StateSupervisionEditorDialog(supervision_id=dialog.supervision_id)
        self.assertEqual(
            [row.title for row in reopened._active_timeline_items()],
            ["První upraveno", "Třetí"],
        )
        self.assertEqual(len(reopened._active_timeline_items()), 2)
        reopened.close()
        dialog.close()

    def test_07_wrapper_keep_existing_and_empty_collection(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Keep {self.marker}"
        )
        state_supervision_required_document_service.create_document(
            record.id, title="Doklad"
        )
        item = state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Průběh"
        )

        state_supervision_service.save_supervision_with_documents(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            documents=[
                StateSupervisionRequiredDocumentDraft(
                    id=state_supervision_required_document_service.list_documents(
                        record.id
                    )[0].id,
                    title="Doklad",
                )
            ],
        )
        self.assertEqual(_active_titles(record.id), ["Průběh"])
        self.assertTrue(
            state_supervision_timeline_item_service.get_timeline_item(item.id).active
        )

        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            documents=KEEP_EXISTING,
            timeline_items=KEEP_EXISTING,
        )
        self.assertEqual(_active_document_titles(record.id), ["Doklad"])
        self.assertEqual(_active_titles(record.id), ["Průběh"])

        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            documents=[],
            timeline_items=[],
        )
        self.assertEqual(_active_document_titles(record.id), [])
        self.assertEqual(_active_titles(record.id), [])
        self.assertEqual(
            len(
                state_supervision_required_document_service.list_documents(
                    record.id, include_inactive=True
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                state_supervision_timeline_item_service.list_timeline_items(
                    record.id, include_inactive=True
                )
            ),
            1,
        )

    def test_08_atomic_rollback_and_single_commit(self) -> None:
        before_s = _count("state_supervisions")
        before_d = _count("state_supervision_required_documents")
        before_t = _count("state_supervision_timeline_items")
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": "   "},
                documents=[StateSupervisionRequiredDocumentDraft(title="A")],
                timeline_items=[StateSupervisionTimelineItemDraft(title="B")],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)

        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"OIP {self.marker}"},
                documents=[
                    StateSupervisionRequiredDocumentDraft(title="Platný"),
                    StateSupervisionRequiredDocumentDraft(title="  "),
                ],
                timeline_items=[StateSupervisionTimelineItemDraft(title="Úkon")],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)

        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"OIP {self.marker}"},
                documents=[StateSupervisionRequiredDocumentDraft(title="Doklad")],
                timeline_items=[
                    StateSupervisionTimelineItemDraft(title="Platný"),
                    StateSupervisionTimelineItemDraft(title="  "),
                ],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Rollback {self.marker}")
        self._add_working(dialog, title="Pracovní")
        with patch.object(
            state_supervision_timeline_item_service,
            "save_timeline_batch",
            side_effect=StateSupervisionError("umělá chyba průběhu"),
        ):
            with patch.object(QMessageBox, "warning"):
                self.assertFalse(self._save(dialog))
        self.assertIsNone(dialog.supervision_id)
        self.assertIsNone(dialog._active_timeline_items()[0].id)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

        source = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)

        commits = []
        original = Session.commit

        def _spy(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with patch.object(Session, "commit", _spy):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Commit {self.marker}"},
                documents=[StateSupervisionRequiredDocumentDraft(title="A")],
                timeline_items=[
                    StateSupervisionTimelineItemDraft(title="X"),
                    StateSupervisionTimelineItemDraft(title="Y"),
                ],
            )
        self.assertEqual(len(commits), 1)

    def test_09_no_write_on_open_and_agenda_four_tabs(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Open {self.marker}"
        )
        state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Načíst"
        )
        before_s = _count("state_supervisions")
        before_t = _count("state_supervision_timeline_items")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertIsInstance(dialog._editor, EditorDialogController)
        dialog.tabs.setCurrentIndex(2)
        dialog.close()
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        self.assertIsInstance(page.state_supervision_tab, StateSupervisionTab)

    def test_10_subdialog_fields_and_window_modal(self) -> None:
        sub = StateSupervisionTimelineItemDialog(is_new=True)
        self.assertEqual(sub.windowModality(), Qt.WindowModality.WindowModal)
        self.assertTrue(sub.occurred_at_edit)
        self.assertTrue(sub.title_edit)
        self.assertTrue(sub.place_edit)
        self.assertTrue(sub.notes_edit)
        sub.title_edit.setText("  ")
        with patch.object(QMessageBox, "warning") as warning:
            sub._on_save()
            warning.assert_called()
        self.assertIsNone(sub.result_draft)
        sub.title_edit.setText("Kontrola provozu vlečky")
        sub._on_save()
        self.assertEqual(sub.result_draft.title, "Kontrola provozu vlečky")
        self.assertIsNone(sub.result_draft.occurred_at)
        self.assertIsNone(sub.result_draft.place)
        sub.close()

        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("save_supervision_bundle", source)
        self.assertNotIn("DELETE FROM", source)
        self.assertEqual(source.count("create_supervision("), 0)


if __name__ == "__main__":
    unittest.main()
