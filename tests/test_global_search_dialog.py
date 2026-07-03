import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.search.constants import SOURCE_TYPE_TASK
    from core.search.global_search_service import GlobalSearchService
    from core.search.search_result import SearchResult
    from core.search.ui.global_search_dialog import GlobalSearchDialog


class GlobalSearchDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _sample_result(self, *, source_id: int = 1, title: str = "Kontrola OOPP") -> SearchResult:
        return SearchResult(
            source_type=SOURCE_TYPE_TASK,
            source_id=source_id,
            title=title,
            subtitle="Aktivní | Novák",
            description="Doplnit OOPP",
            module_key="ukoly",
            module_label="Úkoly",
            priority=100,
        )

    def test_dialog_can_be_created(self) -> None:
        dialog = GlobalSearchDialog()

        self.assertIsNotNone(dialog._search_edit)
        self.assertIsNotNone(dialog._results_list)
        self.assertIsNotNone(dialog._status_label)

    def test_short_query_shows_hint(self) -> None:
        service = MagicMock(spec=GlobalSearchService)
        dialog = GlobalSearchDialog(search_service=service)

        dialog._search_edit.setText("a")

        self.assertEqual(dialog._status_label.text(), GlobalSearchDialog.STATUS_QUERY_TOO_SHORT)
        self.assertEqual(dialog.result_items(), [])
        service.search.assert_not_called()

    def test_query_calls_global_search_service(self) -> None:
        service = MagicMock(spec=GlobalSearchService)
        service.search.return_value = [self._sample_result()]
        dialog = GlobalSearchDialog(search_service=service)

        dialog._search_edit.setText("oop")

        service.search.assert_called_once_with("oop")

    def test_results_are_displayed(self) -> None:
        service = MagicMock(spec=GlobalSearchService)
        service.search.return_value = [
            self._sample_result(source_id=1, title="Kontrola OOPP"),
            self._sample_result(source_id=2, title="Revize hydrantů"),
        ]
        dialog = GlobalSearchDialog(search_service=service)

        dialog._search_edit.setText("kontrola")

        self.assertEqual(len(dialog.result_items()), 2)
        titles = [item.title for item in dialog.result_items()]
        self.assertIn("Kontrola OOPP", titles)
        self.assertIn("Revize hydrantů", titles)

    def test_empty_results_show_message(self) -> None:
        service = MagicMock(spec=GlobalSearchService)
        service.search.return_value = []
        dialog = GlobalSearchDialog(search_service=service)

        dialog._search_edit.setText("xyz")

        self.assertEqual(dialog._status_label.text(), GlobalSearchDialog.STATUS_EMPTY)
        self.assertEqual(dialog.result_items(), [])

    def test_esc_closes_dialog(self) -> None:
        dialog = GlobalSearchDialog()
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )

        dialog.keyPressEvent(event)

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)


if __name__ == "__main__":
    unittest.main()
