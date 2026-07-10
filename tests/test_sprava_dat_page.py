import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QLabel, QFrame, QPushButton, QTabWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.windows.main_window import MainWindow
    from moduly.sprava_dat.ui.sprava_dat_page import (
        TAB_BACKUP,
        TAB_CODEBOOKS,
        TAB_DIAGNOSTICS,
        TAB_TRANSFER,
        SpravaDatPage,
    )


class SpravaDatPageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_page_contains_four_tabs(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        assert tabs is not None
        self.assertEqual(
            [tabs.tabText(index) for index in range(tabs.count())],
            [TAB_BACKUP, TAB_TRANSFER, TAB_CODEBOOKS, TAB_DIAGNOSTICS],
        )

    def test_page_opens_on_backup_tab(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        assert tabs is not None
        self.assertEqual(tabs.tabText(tabs.currentIndex()), TAB_BACKUP)

    def test_page_title_is_sprava_dat(self) -> None:
        page = SpravaDatPage()

        labels = [label.text() for label in page.findChildren(QLabel)]
        self.assertIn("Správa dat", labels)


class MainWindowSpravaDatTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def _sidebar_button_texts(self) -> list[str]:
        sidebar = self.window.findChild(QFrame, "Sidebar")
        self.assertIsNotNone(sidebar)
        return [button.text() for button in sidebar.findChildren(QPushButton)]

    def test_sidebar_contains_sprava_dat_above_nastaveni(self) -> None:
        texts = self._sidebar_button_texts()

        self.assertIn("Správa dat", texts)
        self.assertIn("⚙️ Nastavení", texts)
        self.assertLess(texts.index("Správa dat"), texts.index("⚙️ Nastavení"))

    def test_show_sprava_dat_opens_page(self) -> None:
        self.window._show("sprava_dat")

        self.assertIs(self.window.stack.currentWidget(), self.window._page_widgets["sprava_dat"])
        self.assertIsInstance(self.window._page_widgets["sprava_dat"], SpravaDatPage)

    def test_other_menu_items_remain_functional(self) -> None:
        self.window._show("ukoly")
        self.assertIs(self.window.stack.currentWidget(), self.window._page_widgets["ukoly"])

        self.window._show("sprava_dat")
        self.assertIs(self.window.stack.currentWidget(), self.window._page_widgets["sprava_dat"])

        self.window._show("nastaveni")
        self.assertIs(self.window.stack.currentWidget(), self.window._page_widgets["nastaveni"])


if __name__ == "__main__":
    unittest.main()
