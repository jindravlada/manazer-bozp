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

        self.assertTrue(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertFalse(dialog.content_stack.isVisibleTo(dialog))
        self.assertIn(KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT, dialog._empty_state_label.text())

    def test_dialog_process_selection_hides_hint(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        assert first_process is not None

        dialog.knowledge_tree.setCurrentItem(first_process)

        self.assertFalse(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertTrue(dialog.content_stack.isVisibleTo(dialog))
        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_PROCESS)
        self.assertTrue(dialog.center_title_label.text())
        self.assertTrue(dialog._apply_btn.isEnabled())

    def test_dialog_section_selection_hides_hint(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        assert first_process is not None
        self.assertGreater(first_process.childCount(), 0)

        first_section = first_process.child(0)
        dialog.knowledge_tree.setCurrentItem(first_section)

        self.assertFalse(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertTrue(dialog.content_stack.isVisibleTo(dialog))
        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_SECTION)
        self.assertTrue(dialog.center_title_label.text())
        self.assertTrue(dialog._apply_btn.isEnabled())
        self.assertNotIn(
            KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT,
            {
                label.text()
                for label in dialog.center_panel.findChildren(QLabel)
                if label.isVisibleTo(dialog.center_panel)
            },
        )

    def test_dialog_opens_with_process_and_criterion_context(self) -> None:
        dialog = AudityKnowledgeEditorDialog(
            process_id="urazy_mimo_udalosti",
            criterion_id="evidence_hlaseni_urazu",
        )

        self.assertEqual(dialog._current_process_id, "urazy_mimo_udalosti")
        self.assertEqual(dialog._current_section_id, "evidence_hlaseni_urazu")
        self.assertFalse(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_SECTION)

    def test_dialog_opens_with_process_context_only(self) -> None:
        dialog = AudityKnowledgeEditorDialog(process_id="urazy_mimo_udalosti")

        self.assertEqual(dialog._current_process_id, "urazy_mimo_udalosti")
        self.assertFalse(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_PROCESS)

    def test_dialog_invalid_context_falls_back_to_hint(self) -> None:
        dialog = AudityKnowledgeEditorDialog(
            process_id="neexistujici_proces",
            criterion_id="neexistujici_kriterium",
        )

        self.assertTrue(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertFalse(dialog.content_stack.isVisibleTo(dialog))

    def test_footer_buttons_remain_in_layout(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        dialog.resize(640, 420)
        dialog.show()
        AudityKnowledgeEditorDialogTestCase._app.processEvents()

        self.assertTrue(dialog._save_close_btn.isVisible())
        self.assertTrue(dialog._close_btn.isVisible())
        self.assertEqual(dialog._close_btn.text(), "Zavřít")

        dialog.close()

    def test_exec_maximized_shows_dialog_maximized(self) -> None:
        from PySide6.QtWidgets import QDialog

        from core.widgets.dialog_utils import exec_maximized, prepare_work_dialog_maximized

        dialog = AudityKnowledgeEditorDialog()
        with (
            patch(
                "core.widgets.dialog_utils.prepare_work_dialog_maximized",
                wraps=prepare_work_dialog_maximized,
            ) as mock_prepare,
            patch.object(dialog, "showMaximized") as mock_show,
            patch.object(QDialog, "exec", return_value=0),
        ):
            exec_maximized(dialog)

        mock_prepare.assert_called_once_with(dialog)
        mock_show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
