"""AGENDA-GLOBAL-SEARCH-UX-1: navigace úkolů z globálního vyhledávání do Agendy."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    from core.search.bootstrap import build_default_search_result_opener
    from core.search.constants import SOURCE_TYPE_TASK
    from core.search.global_search_result import GlobalSearchResult
    from core.search.global_search_service import GlobalSearchService
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import ITEM_TYPE_TASK, STATUS_MODE_ALL
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_TASKS_MEETINGS
    from moduly.ukoly.sluzby.task_service import task_service


class AgendaGlobalSearchUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_opener_shows_agenda_not_ukoly(self) -> None:
        task = task_service.create_task(title="GS UX1 úkol opener")
        service = GlobalSearchService(result_opener=build_default_search_result_opener())
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=task.id,
            title=task.title,
            module_key="ukoly",
            group_label="Úkoly",
        )

        host = MagicMock()
        agenda_page = MagicMock()
        ukoly_page = MagicMock()
        host._page_widgets = {"agenda": agenda_page, "ukoly": ukoly_page}

        self.assertTrue(service.open_result(result, host))
        host._show.assert_called_once_with("agenda")
        agenda_page.open_task.assert_called_once_with(task.id)
        ukoly_page.open_task.assert_not_called()

    def test_agenda_open_task_switches_tab_and_opens_dialog(self) -> None:
        task = task_service.create_task(title="GS UX1 agenda open_task")
        page = AgendaPage()
        page.tabs.setCurrentIndex(1)

        with patch("moduly.agenda.ui.agenda_page.TaskDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            page.open_task(task.id)

        self.assertEqual(page.tabs.tabText(page.tabs.currentIndex()), TAB_TASKS_MEETINGS)
        self.assertEqual(page.status_filter.currentText(), STATUS_MODE_ALL)
        mock_dialog.assert_called_once()
        selected = page.table.selected_item()
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.item_type, ITEM_TYPE_TASK)
        self.assertEqual(selected.source_id, task.id)

    def test_main_window_global_search_stays_on_agenda(self) -> None:
        window = MainWindow()
        task = task_service.create_task(title="GS UX1 main window")
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=task.id,
            title=task.title,
            module_key="ukoly",
            group_label="Úkoly",
        )

        agenda_page = window._page_widgets["agenda"]
        with patch.object(agenda_page, "open_task") as mock_open:
            window._open_global_search_result(result)

        mock_open.assert_called_once_with(task.id)
        self.assertIs(window.current_page_widget(), agenda_page)
        self.assertIsNot(window.current_page_widget(), window._page_widgets["ukoly"])


if __name__ == "__main__":
    unittest.main()
