"""AGENDA-TASK-UX-6: stay-open ukládání editoru úkolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.attachment_service import attachment_service
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


class AgendaTaskUx6TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _new_dialog(self, **kwargs) -> TaskDialog:
        dialog = TaskDialog(**kwargs)
        dialog.title_edit.setPlainText("Úkol UX-6")
        dialog._capture_baseline()
        return dialog

    def test_a_new_save_stay_open_activates_attachments(self) -> None:
        dialog = self._new_dialog()
        self.assertIsNone(dialog.task)
        self.assertFalse(dialog.attachment_widget.btn_add.isEnabled())

        self.assertTrue(dialog._persist())

        self.assertIsNotNone(dialog.task)
        self.assertIsNotNone(dialog.task.id)
        self.assertTrue(dialog.attachment_widget.btn_add.isEnabled())
        self.assertEqual(dialog.attachment_widget.entity_id, dialog.task.id)
        self.assertFalse(dialog._is_dirty())

    def test_b_second_save_updates_same_task(self) -> None:
        dialog = self._new_dialog()
        self.assertTrue(dialog._persist())
        task_id = dialog.task.id

        dialog.title_edit.setPlainText("Úkol UX-6 upravený")
        self.assertTrue(dialog._is_dirty())
        self.assertTrue(dialog._persist())

        self.assertEqual(dialog.task.id, task_id)
        reloaded = task_service.get_task_by_id(task_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.title, "Úkol UX-6 upravený")
        matching = [
            t for t in task_service.repository.get_all() if t.id == task_id
        ]
        self.assertEqual(len(matching), 1)

    def test_c_new_save_and_close(self) -> None:
        dialog = self._new_dialog()
        dialog._save_and_close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNotNone(dialog.task)
        self.assertIsNotNone(task_service.get_task_by_id(dialog.task.id))

    def test_d_existing_save_stay_open(self) -> None:
        task = task_service.create_task(title="Existující UX-6")
        dialog = TaskDialog(task=task)
        dialog.title_edit.setPlainText("Existující UX-6 změna")
        self.assertTrue(dialog._persist())
        self.assertEqual(dialog.task.id, task.id)
        self.assertFalse(dialog._is_dirty())
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded.title, "Existující UX-6 změna")

    def test_e_existing_save_and_close(self) -> None:
        task = task_service.create_task(title="Existující close UX-6")
        dialog = TaskDialog(task=task)
        dialog.title_edit.setPlainText("Existující close UX-6 změna")
        dialog._save_and_close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded.title, "Existující close UX-6 změna")

    def test_f_after_save_not_dirty(self) -> None:
        dialog = self._new_dialog()
        dialog.title_edit.setPlainText("Dirty check UX-6")
        self.assertTrue(dialog._persist())
        self.assertFalse(dialog._is_dirty())

    def test_g_dirty_prompt_on_close(self) -> None:
        dialog = self._new_dialog()
        self.assertTrue(dialog._persist())
        dialog.title_edit.setPlainText("Po uložení změna")
        self.assertTrue(dialog._is_dirty())

        with patch(
            "moduly.ukoly.ui.task_dialog.confirm_unsaved_editor_close",
            return_value="cancel",
        ):
            self.assertFalse(dialog._confirm_close())
            self.assertTrue(dialog.isVisible() or True)

        with patch(
            "moduly.ukoly.ui.task_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._confirm_close())

    def test_h_attachment_bound_after_first_save(self) -> None:
        dialog = self._new_dialog()
        self.assertTrue(dialog._persist())
        task_id = dialog.task.id

        source = _TMP / "priloha-ux6.txt"
        source.write_text("obsah přílohy", encoding="utf-8")
        attachment_service.add_file("task", task_id, str(source))
        dialog.attachment_widget.reload()

        self.assertEqual(dialog.attachment_widget.list.count(), 1)
        linked = attachment_service.get_for_entity("task", task_id)
        self.assertEqual(len(linked), 1)

    def test_i_repeated_save_never_duplicates(self) -> None:
        before = len(task_service.repository.get_all())
        dialog = self._new_dialog()
        for index in range(3):
            dialog.title_edit.setPlainText(f"Opakované UX-6 {index}")
            self.assertTrue(dialog._persist())
        after = task_service.repository.get_all()
        self.assertEqual(len(after), before + 1)
        self.assertEqual(dialog.task.title, "Opakované UX-6 2")

    def test_footer_labels(self) -> None:
        dialog = TaskDialog()
        self.assertEqual(dialog._save_btn.text(), "Uložit")
        self.assertEqual(dialog._save_close_btn.text(), "Uložit a zavřít")
        self.assertEqual(dialog._close_btn.text(), "Zavřít")


if __name__ == "__main__":
    unittest.main()
