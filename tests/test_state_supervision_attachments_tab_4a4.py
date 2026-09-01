"""STATE-SUPERVISION-ATTACHMENTS-TAB-4A4: samostatná záložka příloh."""

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

from PySide6.QtWidgets import QApplication, QGroupBox, QMessageBox, QTabWidget, QTableWidget
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

    from core.services.attachment_service import attachment_service
    from core.services.storage_service import storage_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_RESTORE,
        ATTACHMENT_STATUS_NEW,
        ATTACHMENT_STATUS_REMOVE,
        ATTACHMENT_STATUS_SAVED,
        ATTACHMENTS_HINT,
        CLOSED_AT_REQUIRED_MESSAGE,
        COL_ATTACHMENT_STATUS,
        ENTITY_STATE_SUPERVISION,
        GROUP_ATTACHMENTS,
        GROUP_COMPLETION_CLOSE,
        GROUP_OBJECTIONS,
        GROUP_PROTOCOL,
        GROUP_RESULT,
        STATUS_CLOSED,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_attachment_staging_widget import (
        StateSupervisionAttachmentStagingWidget,
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


class StateSupervisionAttachmentsTab4a4TestCase(unittest.TestCase):
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
        self.sources = Path(tempfile.mkdtemp(prefix="ss-attach-tab-"))
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

    def test_01_five_tabs_widget_only_on_attachments(self) -> None:
        dialog = StateSupervisionEditorDialog()
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertEqual(
            titles,
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        self.assertEqual(dialog.tabs.count(), 5)
        self.assertEqual(dialog.tabs.currentIndex(), 0)
        self.assertEqual(dialog._attachments_tab_index, 4)
        widgets = dialog.findChildren(StateSupervisionAttachmentStagingWidget)
        self.assertEqual(len(widgets), 1)
        self.assertIs(widgets[0], dialog.attachments_widget)
        conclusion = dialog.tabs.widget(3).widget()
        self.assertEqual(
            [box.title() for box in conclusion.findChildren(QGroupBox)],
            [GROUP_RESULT, GROUP_PROTOCOL, GROUP_OBJECTIONS, GROUP_COMPLETION_CLOSE],
        )
        self.assertEqual(
            len(conclusion.findChildren(StateSupervisionAttachmentStagingWidget)),
            0,
        )
        self.assertEqual(len(conclusion.findChildren(QTableWidget)), 0)
        page = dialog.tabs.widget(4)
        self.assertEqual(page.findChildren(StateSupervisionAttachmentStagingWidget), widgets)
        self.assertFalse(isinstance(page, QGroupBox))
        self.assertEqual(
            [box.title() for box in page.findChildren(QGroupBox)],
            [],
        )
        self.assertEqual(dialog.attachments_widget.hint.text(), ATTACHMENTS_HINT)
        self.assertNotIn(GROUP_ATTACHMENTS, titles)
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(source.count("self.tabs.addTab("), 5)
        self.assertEqual(source.count("StateSupervisionAttachmentStagingWidget("), 1)
        self.assertNotIn("_build_attachments_section", source)
        self.assertNotIn("AttachmentWidget", source)

        page_agenda = AgendaPage()
        self.assertEqual(page_agenda.tabs.count(), 4)
        self.assertEqual(page_agenda.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page_agenda.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page_agenda.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page_agenda.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page_agenda.tabs, QTabWidget)
        page_agenda.close()
        dialog.close()

    def test_02_add_on_fifth_tab_dirty_and_tab_switch(self) -> None:
        source = self._source("oznameni.pdf")
        dialog = StateSupervisionEditorDialog()
        self.assertIsNone(dialog.supervision_id)
        dialog.tabs.setCurrentIndex(4)
        self.assertFalse(dialog._editor.is_dirty())
        before_db = _count("attachments")
        dialog.attachments_widget.add_paths([str(source)])
        self.assertEqual(_count("attachments"), before_db)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        self.assertEqual(
            dialog.attachments_widget.table.item(0, COL_ATTACHMENT_STATUS).text(),
            ATTACHMENT_STATUS_NEW,
        )
        dialog.tabs.setCurrentIndex(0)
        dialog.tabs.setCurrentIndex(4)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.attachments_widget.table.selectRow(0)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertFalse(dialog._editor.is_dirty())
        dialog.attachments_widget.add_paths([str(source)])
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        dialog.close()
        self.assertEqual(_count("attachments"), 0)

    def test_03_save_paths_reset_staging_and_open(self) -> None:
        record = self._create()
        keep = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION,
            record.id,
            str(self._source("ulozena.txt", "keep")),
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.tabs.setCurrentIndex(4)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(
            dialog.attachments_widget.table.item(0, COL_ATTACHMENT_STATUS).text(),
            ATTACHMENT_STATUS_SAVED,
        )
        with patch(
            "moduly.statni_dozor.ui.state_supervision_attachment_staging_widget.open_local_file",
            return_value=True,
        ) as opener:
            dialog.attachments_widget.table.selectRow(0)
            dialog.attachments_widget.open_selected()
            opener.assert_called()
        self.assertFalse(dialog._editor.is_dirty())

        staged = self._source("nova.pdf")
        dialog.attachments_widget.add_paths([str(staged)])
        dialog.attachments_widget.table.selectRow(
            dialog.attachments_widget.table.rowCount() - 1
        )
        with patch(
            "moduly.statni_dozor.ui.state_supervision_attachment_staging_widget.open_local_file",
            return_value=True,
        ) as opener:
            dialog.attachments_widget.open_selected()
            self.assertEqual(Path(opener.call_args.args[0]), staged)

        dialog.attachments_widget.table.selectRow(0)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertEqual(
            dialog.attachments_widget.table.item(0, COL_ATTACHMENT_STATUS).text(),
            ATTACHMENT_STATUS_REMOVE,
        )
        self.assertEqual(dialog.attachments_widget.btn_remove.text(), ACTION_RESTORE)
        dialog.attachments_widget.remove_or_restore_selected()
        self.assertEqual(
            dialog.attachments_widget.table.item(0, COL_ATTACHMENT_STATUS).text(),
            ATTACHMENT_STATUS_SAVED,
        )
        old_staging = dialog._attachment_staging
        extra = self._source("dalsi.pdf")
        dialog.attachments_widget.add_paths([str(extra)])
        with patch.object(dialog, "accept") as accept:
            with patch.object(QMessageBox, "warning"):
                dialog._save_and_close()
            accept.assert_called_once()
        self.assertIsNot(dialog._attachment_staging, old_staging)
        self.assertFalse(dialog._attachment_staging.has_changes())
        names = {
            row.filename
            for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, record.id
            )
        }
        self.assertIn(keep.filename, names)
        self.assertIn("dalsi.pdf", names)
        dialog.close()

        dialog2 = StateSupervisionEditorDialog()
        dialog2.tabs.setCurrentIndex(4)
        dialog2.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog2.attachments_widget.add_paths([str(self._source("jedna.pdf"))])
        self.assertTrue(self._save(dialog2))
        self.assertEqual(
            dialog2.attachments_widget.table.item(0, COL_ATTACHMENT_STATUS).text(),
            ATTACHMENT_STATUS_SAVED,
        )
        self.assertFalse(dialog2._attachment_staging.has_changes())
        self.assertTrue(self._save(dialog2))
        self.assertEqual(
            len(
                attachment_service.get_for_entity(
                    ENTITY_STATE_SUPERVISION, dialog2.supervision_id
                )
            ),
            1,
        )
        dialog2.close()

    def test_04_attachment_error_switches_tab_others_do_not(self) -> None:
        missing = self.sources / "neni.pdf"
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog.tabs.setCurrentIndex(0)
        dialog.attachments_widget.add_paths([str(missing)])
        self.assertFalse(self._save(dialog))
        self.assertEqual(dialog.tabs.currentIndex(), 4)
        self.assertEqual(dialog._attachment_staging.pending_add_paths, [str(missing)])
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

        first = self._source("prvni.txt")
        second = self._source("druhy.txt")
        dialog2 = StateSupervisionEditorDialog()
        dialog2.authority_combo.setCurrentText(f"Kopírování {self.marker}")
        dialog2.tabs.setCurrentIndex(2)
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
        self.assertEqual(dialog2.tabs.currentIndex(), 4)
        self.assertEqual(len(dialog2._attachment_staging.pending_add_paths), 2)
        dialog2.close()

        dialog3 = StateSupervisionEditorDialog()
        dialog3.authority_combo.setCurrentText(f"Uzavření {self.marker}")
        dialog3.status_combo.setCurrentIndex(dialog3.status_combo.findData(STATUS_CLOSED))
        dialog3.tabs.setCurrentIndex(0)
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(dialog3._editor._run_save())
            self.assertIn(CLOSED_AT_REQUIRED_MESSAGE, warning.call_args.args)
        self.assertEqual(dialog3.tabs.currentIndex(), 3)
        dialog3.close()

        dialog4 = StateSupervisionEditorDialog()
        dialog4.authority_combo.setCurrentText(f"Průběh {self.marker}")
        dialog4.tabs.setCurrentIndex(0)
        dialog4.attachments_widget.add_paths([str(self._source("kolekce.pdf"))])
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_timeline_item_service."
            "state_supervision_timeline_item_service.save_timeline_batch",
            side_effect=StateSupervisionError("umělá chyba průběhu"),
        ):
            self.assertFalse(self._save(dialog4))
        self.assertEqual(dialog4.tabs.currentIndex(), 0)
        self.assertTrue(dialog4._attachment_staging.has_changes())
        dialog4.close()

        existing = self._create(authority_name=f"Commit {self.marker}")
        created = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION,
            existing.id,
            str(self._source("ponechat.txt")),
        )
        dialog5 = StateSupervisionEditorDialog(supervision_id=existing.id)
        dialog5.tabs.setCurrentIndex(1)
        dialog5.attachments_widget.table.selectRow(0)
        dialog5.attachments_widget.remove_or_restore_selected()
        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            self.assertFalse(self._save(dialog5))
        self.assertEqual(dialog5.tabs.currentIndex(), 1)
        self.assertTrue(dialog5._attachment_staging.is_marked_for_removal(created.id))
        dialog5.close()

    def test_05_open_attachments_tab_does_not_write(self) -> None:
        record = self._create()
        attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("open.txt"))
        )
        before_s = _count("state_supervisions")
        before_a = _count("attachments")
        files_before = list(storage_service.attachments_dir.rglob("*"))
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.tabs.setCurrentIndex(4)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._attachment_staging.has_changes())
        dialog.close()
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("attachments"), before_a)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*")), files_before)


if __name__ == "__main__":
    unittest.main()
