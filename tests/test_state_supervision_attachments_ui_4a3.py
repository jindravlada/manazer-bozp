"""STATE-SUPERVISION-ATTACHMENTS-UI-4A3: přílohy spisu kontroly."""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QTabWidget,
)
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

    import core.services.attachment_service as attachment_module

    importlib.reload(attachment_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.models.attachment_staging import AttachmentStagingState
    from core.services.attachment_service import attachment_service
    from core.services.storage_service import storage_service
    from core.widgets.editor_dialog_controller import EditorDialogController
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_ADD_ATTACHMENTS,
        ACTION_OPEN,
        ACTION_REMOVE,
        ACTION_RESTORE,
        ACTION_SAVE_AND_CLOSE,
        ATTACHMENT_COLUMN_HEADERS,
        ATTACHMENT_FILE_FILTER,
        ATTACHMENT_FILE_MISSING,
        ATTACHMENT_STATUS_NEW,
        ATTACHMENT_STATUS_REMOVE,
        ATTACHMENT_STATUS_SAVED,
        ATTACHMENTS_HINT,
        COL_ATTACHMENT_NAME,
        COL_ATTACHMENT_SIZE,
        COL_ATTACHMENT_STATUS,
        COL_ATTACHMENT_TYPE,
        EMPTY_ATTACHMENTS,
        ENTITY_STATE_SUPERVISION,
        GROUP_ATTACHMENTS,
        GROUP_COMPLETION_CLOSE,
        GROUP_RESULT,
        TAB_ANNOUNCEMENT,
        TAB_CONCLUSION,
        TAB_COURSE,
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
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _write(path: Path, text: str = "obsah") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class StateSupervisionAttachmentsUi4a3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        importlib.reload(attachment_module)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.sources = Path(tempfile.mkdtemp(prefix="ss-attach-ui-"))
        attachments_dir = storage_service.attachments_dir
        if attachments_dir.exists():
            shutil.rmtree(attachments_dir)
        attachments_dir.mkdir(parents=True, exist_ok=True)
        session = session_module.get_session()
        try:
            from sqlalchemy import delete

            from core.models.attachment import Attachment

            session.execute(delete(Attachment))
            session.commit()
        finally:
            session.close()

    def tearDown(self) -> None:
        shutil.rmtree(self.sources, ignore_errors=True)

    def _source(self, name: str, text: str = "obsah") -> Path:
        return _write(self.sources / name, text)

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        with patch.object(QMessageBox, "warning"):
            return bool(dialog._editor._run_save())

    def _create(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _status(self, dialog: StateSupervisionEditorDialog, row: int) -> str:
        item = dialog.attachments_widget.table.item(row, COL_ATTACHMENT_STATUS)
        return item.text() if item is not None else ""

    def _name(self, dialog: StateSupervisionEditorDialog, row: int) -> str:
        item = dialog.attachments_widget.table.item(row, COL_ATTACHMENT_NAME)
        return item.text() if item is not None else ""

    def test_01_four_tabs_section_hint_empty_and_buttons(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.tabs.count(), 4)
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],
            [TAB_ANNOUNCEMENT, TAB_SUBJECT_PREPARATION, TAB_COURSE, TAB_CONCLUSION],
        )
        self.assertEqual(dialog.minimumWidth(), 640)
        self.assertEqual(dialog.minimumHeight(), 480)
        scroll = dialog.tabs.widget(3)
        page = scroll.widget()
        groups = [box.title() for box in page.findChildren(QGroupBox)]
        self.assertEqual(groups[-1], GROUP_ATTACHMENTS)
        self.assertGreater(groups.index(GROUP_ATTACHMENTS), groups.index(GROUP_COMPLETION_CLOSE))
        self.assertGreater(groups.index(GROUP_COMPLETION_CLOSE), groups.index(GROUP_RESULT))
        widget = dialog.attachments_widget
        self.assertEqual(widget.hint.text(), ATTACHMENTS_HINT)
        self.assertEqual(widget.empty_label.text(), EMPTY_ATTACHMENTS)
        self.assertFalse(widget.empty_label.isHidden())
        self.assertFalse(widget.table.isVisible())
        self.assertEqual(
            [
                widget.table.horizontalHeaderItem(i).text()
                for i in range(widget.table.columnCount())
            ],
            ATTACHMENT_COLUMN_HEADERS,
        )
        self.assertEqual(widget.table.textElideMode(), Qt.TextElideMode.ElideRight)
        self.assertFalse(widget.table.isSortingEnabled())
        self.assertGreaterEqual(widget.table.minimumHeight(), 140)
        self.assertEqual(widget.btn_add.text(), ACTION_ADD_ATTACHMENTS)
        self.assertEqual(widget.btn_open.text(), ACTION_OPEN)
        self.assertEqual(widget.btn_remove.text(), ACTION_REMOVE)
        self.assertTrue(widget.btn_add.isEnabled())
        self.assertFalse(widget.btn_open.isEnabled())
        self.assertFalse(widget.btn_remove.isEnabled())
        self.assertIn("Všechny soubory", ATTACHMENT_FILE_FILTER)
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(source.count("self.tabs.addTab("), 4)
        self.assertNotIn("AttachmentWidget", source)
        self.assertIn("attachments=self._attachment_staging", source)
        self.assertNotIn("save_button.setEnabled(True)", source)
        self.assertIs(widget.staging, dialog._attachment_staging)
        dialog.close()

    def test_02_new_control_add_without_id_dirty_duplicate_and_discard(self) -> None:
        source = self._source("oznameni.pdf", "pdf")
        dialog = StateSupervisionEditorDialog()
        self.assertIsNone(dialog.supervision_id)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        before_files = list(storage_service.attachments_dir.rglob("*"))
        before_db = _count("attachments")
        with patch.object(
            QFileDialog, "getOpenFileNames", return_value=([str(source)], "")
        ):
            dialog.attachments_widget.add_files()
        self.assertEqual(_count("attachments"), before_db)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*")), before_files)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        self.assertEqual(dialog.attachments_widget.table.rowCount(), 1)
        self.assertEqual(self._status(dialog, 0), ATTACHMENT_STATUS_NEW)
        self.assertEqual(self._name(dialog, 0), "oznameni.pdf")
        type_item = dialog.attachments_widget.table.item(0, COL_ATTACHMENT_TYPE)
        self.assertEqual(type_item.text(), "PDF")
        self.assertEqual(dialog._attachment_staging.pending_add_paths, [str(source)])
        self.assertFalse(dialog.attachments_widget.btn_open.isEnabled())
        self.assertFalse(dialog.attachments_widget.btn_remove.isEnabled())

        with patch.object(QMessageBox, "information") as info:
            dialog.attachments_widget.add_paths([str(source)])
            info.assert_called()
        self.assertEqual(len(dialog._attachment_staging.pending_add_paths), 1)

        dialog.attachments_widget.table.selectRow(0)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertFalse(dialog._attachment_staging.has_changes())
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.attachments_widget.add_paths([str(source)])
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        dialog.close()
        self.assertEqual(_count("attachments"), 0)
        self.assertEqual(
            list((storage_service.attachments_dir / ENTITY_STATE_SUPERVISION).rglob("*"))
            if (storage_service.attachments_dir / ENTITY_STATE_SUPERVISION).exists()
            else [],
            [],
        )

    def test_03_save_new_parent_and_attachment_resets_staging(self) -> None:
        source = self._source("protokol.pdf", "protokol")
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog.attachments_widget.add_paths([str(source)])
        old_staging = dialog._attachment_staging
        self.assertTrue(self._save(dialog))
        self.assertIsNotNone(dialog.supervision_id)
        self.assertIsNot(dialog._attachment_staging, old_staging)
        self.assertIs(dialog.attachments_widget.staging, dialog._attachment_staging)
        self.assertFalse(dialog._attachment_staging.has_changes())
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertEqual(dialog.attachments_widget.table.rowCount(), 1)
        self.assertEqual(self._status(dialog, 0), ATTACHMENT_STATUS_SAVED)
        rows = attachment_service.get_for_entity(
            ENTITY_STATE_SUPERVISION, dialog.supervision_id
        )
        self.assertEqual(len(rows), 1)
        stored = attachment_service.resolve_path(rows[0])
        self.assertTrue(stored.is_file())
        self.assertEqual(
            stored.parent,
            storage_service.attachments_dir
            / ENTITY_STATE_SUPERVISION
            / str(dialog.supervision_id),
        )
        self.assertTrue(self._save(dialog))
        self.assertEqual(
            len(
                attachment_service.get_for_entity(
                    ENTITY_STATE_SUPERVISION, dialog.supervision_id
                )
            ),
            1,
        )
        dialog.close()

    def test_04_existing_open_mark_restore_and_mixed_save(self) -> None:
        record = self._create()
        keep = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("zustane.txt", "keep"))
        )
        drop = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("odebrat.txt", "drop"))
        )
        drop_path = attachment_service.resolve_path(drop)
        before = _count("attachments")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(_count("attachments"), before)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(dialog.attachments_widget.table.rowCount(), 2)
        self.assertEqual(self._status(dialog, 0), ATTACHMENT_STATUS_SAVED)

        dialog.attachments_widget.table.selectRow(0)
        self.assertFalse(dialog._editor.is_dirty())
        with patch(
            "moduly.statni_dozor.ui.state_supervision_attachment_staging_widget.open_local_file",
            return_value=True,
        ) as opener:
            dialog.attachments_widget.open_selected()
            opener.assert_called()
        self.assertFalse(dialog._editor.is_dirty())
        dialog.tabs.setCurrentIndex(0)
        dialog.tabs.setCurrentIndex(3)
        self.assertFalse(dialog._editor.is_dirty())

        staged = self._source("nova.pdf", "new")
        dialog.attachments_widget.add_paths([str(staged)])
        dialog.attachments_widget.table.selectRow(0)
        with patch(
            "moduly.statni_dozor.ui.state_supervision_attachment_staging_widget.open_local_file",
            return_value=True,
        ) as opener:
            # last row is pending
            dialog.attachments_widget.table.selectRow(
                dialog.attachments_widget.table.rowCount() - 1
            )
            dialog.attachments_widget.open_selected()
            opened = Path(opener.call_args.args[0])
            self.assertEqual(opened, staged)

        drop_row = 0 if self._name(dialog, 0) == drop.filename else 1
        dialog.attachments_widget.table.selectRow(drop_row)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertTrue(drop_path.is_file())
        self.assertEqual(self._status(dialog, drop_row), ATTACHMENT_STATUS_REMOVE)
        self.assertEqual(dialog.attachments_widget.btn_remove.text(), ACTION_RESTORE)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertEqual(self._status(dialog, drop_row), ATTACHMENT_STATUS_SAVED)
        self.assertEqual(dialog.attachments_widget.btn_remove.text(), ACTION_REMOVE)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertTrue(self._save(dialog))
        self.assertFalse(drop_path.exists())
        ids = {
            row.id
            for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, record.id
            )
        }
        self.assertIn(keep.id, ids)
        self.assertNotIn(drop.id, ids)
        names = {
            row.filename
            for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, record.id
            )
        }
        self.assertIn("nova.pdf", names)
        dialog.close()

    def test_05_missing_file_does_not_crash(self) -> None:
        record = self._create()
        created = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("chybi.txt"))
        )
        path = attachment_service.resolve_path(created)
        path.unlink()
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        size = dialog.attachments_widget.table.item(0, COL_ATTACHMENT_SIZE).text()
        self.assertEqual(size, ATTACHMENT_FILE_MISSING)
        dialog.attachments_widget.table.selectRow(0)
        with patch.object(QMessageBox, "warning") as warning:
            dialog.attachments_widget.open_selected()
            warning.assert_called()
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

    def test_06_long_name_tooltip_and_size(self) -> None:
        long_name = ("zápis kontroly " + ("ž" * 40) + ".odt")
        source = self._source(long_name, "x" * 2048)
        dialog = StateSupervisionEditorDialog()
        dialog.attachments_widget.add_paths([str(source)])
        name_item = dialog.attachments_widget.table.item(0, COL_ATTACHMENT_NAME)
        tooltip = name_item.toolTip()
        self.assertIn("zápis kontroly", tooltip)
        self.assertIn(str(source.parent), tooltip)
        self.assertIn(".odt", tooltip)
        size = dialog.attachments_widget.table.item(0, COL_ATTACHMENT_SIZE).text()
        self.assertTrue(size.endswith("kB") or size.endswith("B"))
        self.assertEqual(
            dialog.attachments_widget.table.item(0, COL_ATTACHMENT_TYPE).text(),
            "ODT",
        )
        dialog.close()

    def test_07_save_paths_close_cancel_and_save_close(self) -> None:
        source = self._source("cesta.pdf")
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog.attachments_widget.add_paths([str(source)])
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())

        extra = self._source("dalsi.pdf")
        dialog.attachments_widget.add_paths([str(extra)])
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ):
            self.assertFalse(dialog._editor.request_close())
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(dialog._attachment_staging.pending_add_paths, [str(extra)])

        with patch.object(dialog, "accept") as accept:
            with patch.object(QMessageBox, "warning"):
                dialog._save_and_close()
            accept.assert_called_once()
        self.assertFalse(dialog._attachment_staging.has_changes())
        self.assertEqual(
            len(
                attachment_service.get_for_entity(
                    ENTITY_STATE_SUPERVISION, dialog.supervision_id
                )
            ),
            2,
        )
        self.assertEqual(dialog._save_close_btn.text(), ACTION_SAVE_AND_CLOSE)
        dialog.close()

        dialog2 = StateSupervisionEditorDialog()
        dialog2.authority_combo.setCurrentText(f"CloseSave {self.marker}")
        dialog2.attachments_widget.add_paths([str(self._source("zavrit.pdf"))])
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            self.assertTrue(dialog2._editor.request_close())
        self.assertIsNotNone(dialog2.supervision_id)
        self.assertEqual(
            len(
                attachment_service.get_for_entity(
                    ENTITY_STATE_SUPERVISION, dialog2.supervision_id
                )
            ),
            1,
        )
        dialog2.close()

    def test_08_errors_keep_staging_and_roll_back(self) -> None:
        missing = self.sources / "neni.pdf"
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog.attachments_widget.add_paths([str(missing)])
        staging_before = list(dialog._attachment_staging.pending_add_paths)
        self.assertFalse(self._save(dialog))
        self.assertIsNone(dialog.supervision_id)
        self.assertEqual(dialog._attachment_staging.pending_add_paths, staging_before)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(self._status(dialog, 0), ATTACHMENT_STATUS_NEW)

        first = self._source("prvni.txt")
        second = self._source("druhy.txt")
        dialog2 = StateSupervisionEditorDialog()
        dialog2.authority_combo.setCurrentText(f"Dva {self.marker}")
        dialog2.attachments_widget.add_paths([str(first), str(second)])
        real_copy = shutil.copy2
        calls = {"n": 0}

        def flaky(src, dst, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("disk full")
            return real_copy(src, dst, *args, **kwargs)

        with patch("core.services.attachment_service.shutil.copy2", flaky):
            self.assertFalse(self._save(dialog2))
        self.assertIsNone(dialog2.supervision_id)
        self.assertEqual(len(dialog2._attachment_staging.pending_add_paths), 2)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*.txt")), [])

        existing = self._create(authority_name=f"Původní {self.marker}")
        created = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION,
            existing.id,
            str(self._source("ponechat.txt")),
        )
        path = attachment_service.resolve_path(created)
        dialog3 = StateSupervisionEditorDialog(supervision_id=existing.id)
        dialog3.authority_combo.setCurrentText(f"Změna {self.marker}")
        dialog3._document_drafts.append(
            StateSupervisionRequiredDocumentDraft(title="Doklad")
        )
        dialog3.attachments_widget.table.selectRow(0)
        dialog3.attachments_widget.remove_or_restore_selected()
        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            self.assertFalse(self._save(dialog3))
        loaded = state_supervision_service.get_supervision(existing.id)
        self.assertEqual(loaded.authority_name, f"Původní {self.marker}")
        self.assertEqual(
            state_supervision_required_document_service.list_documents(existing.id),
            [],
        )
        self.assertTrue(path.is_file())
        self.assertEqual(
            [row.id for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, existing.id
            )],
            [created.id],
        )
        self.assertTrue(dialog3._attachment_staging.is_marked_for_removal(created.id))
        self.assertTrue(dialog3._editor.is_dirty())
        dialog.close()
        dialog2.close()
        dialog3.close()

    def test_09_no_write_on_open_and_agenda_tabs(self) -> None:
        record = self._create()
        attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("open.txt"))
        )
        before_s = _count("state_supervisions")
        before_a = _count("attachments")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertIsInstance(dialog._editor, EditorDialogController)
        dialog.tabs.setCurrentIndex(3)
        dialog.close()
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("attachments"), before_a)

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        page.close()


if __name__ == "__main__":
    unittest.main()
