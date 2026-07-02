import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QLabel

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from moduly.audity.constants import (
        KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT,
        KNOWLEDGE_EDITOR_WINDOW_TITLE,
    )
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog


class AudityKnowledgeEditorDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_loads_process_tree(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        self.assertEqual(dialog.windowTitle(), KNOWLEDGE_EDITOR_WINDOW_TITLE)
        self.assertGreaterEqual(dialog.knowledge_tree.topLevelItemCount(), 1)

        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        assert first_process is not None
        self.assertGreaterEqual(first_process.childCount(), 1)

    def test_dialog_shows_hint_before_selection(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        self.assertEqual(dialog.content_stack.currentIndex(), 0)
        hint_page = dialog.content_stack.widget(0)
        hint_label = hint_page.findChild(QLabel)
        self.assertIsNotNone(hint_label)
        assert hint_label is not None
        self.assertIn(KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT, hint_label.text())

    def test_dialog_process_selection_updates_view(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        assert first_process is not None

        dialog.knowledge_tree.setCurrentItem(first_process)

        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_PROCESS)
        self.assertTrue(dialog.center_title_label.text())

    def test_dialog_section_selection_updates_view(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        assert first_process is not None
        self.assertGreater(first_process.childCount(), 0)

        first_section = first_process.child(0)
        dialog.knowledge_tree.setCurrentItem(first_section)

        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_SECTION)
        self.assertTrue(dialog.center_title_label.text())
        self.assertTrue(dialog._save_btn.isEnabled())

    def test_exec_maximized_shows_dialog_maximized(self) -> None:
        from PySide6.QtWidgets import QDialog

        from core.widgets.dialog_utils import exec_maximized

        dialog = AudityKnowledgeEditorDialog()
        with (
            patch.object(dialog, "showMaximized") as mock_show,
            patch.object(QDialog, "exec", return_value=0),
        ):
            exec_maximized(dialog)

        mock_show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
