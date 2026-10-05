"""TESTY-1: založení modulu Testy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.modules.module_manager import ModuleManager
    from core.windows.main_window import MainWindow
    from moduly.testy.constants import MODULE_DESCRIPTION, MODULE_KEY, MODULE_NAME, PAGE_SUBTITLE
    from moduly.testy.module import get_module_definition
    from moduly.testy.ui.testy_page import TestyPage


class Testy1ModuleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_module_registered_with_key_and_name(self) -> None:
        module = get_module_definition()
        self.assertEqual(module.key, MODULE_KEY)
        self.assertEqual(module.key, "testy")
        self.assertEqual(module.name, MODULE_NAME)
        self.assertEqual(module.name, "Testy")
        self.assertEqual(module.description, MODULE_DESCRIPTION)
        self.assertTrue(module.enabled)

        keys = [item.key for item in ModuleManager().get_modules()]
        self.assertIn(MODULE_KEY, keys)
        self.assertLess(keys.index(MODULE_KEY), keys.index("smlouvy_ozo"))

    def test_page_can_be_created(self) -> None:
        module = get_module_definition()
        page = module.page_factory()
        self.assertIsInstance(page, TestyPage)

        labels = {label.objectName(): label.text() for label in page.findChildren(QLabel)}
        self.assertEqual(labels.get("PageTitle"), "Testy")
        self.assertEqual(labels.get("InfoText"), PAGE_SUBTITLE)
        self.assertEqual(
            PAGE_SUBTITLE,
            "Evidence zaměstnanců, příprava testů a evidence výsledků přezkoušení.",
        )

    def test_available_from_main_navigation(self) -> None:
        window = MainWindow()
        sidebar_keys = list(window._sidebar_buttons.keys())

        self.assertIn(MODULE_KEY, sidebar_keys)
        self.assertEqual(window._sidebar_buttons[MODULE_KEY].text(), MODULE_NAME)
        self.assertTrue(window._sidebar_buttons[MODULE_KEY].isEnabled())

        self.assertLess(
            sidebar_keys.index("pravni_pozadavky"),
            sidebar_keys.index(MODULE_KEY),
        )
        self.assertLess(
            sidebar_keys.index(MODULE_KEY),
            sidebar_keys.index("smlouvy_ozo"),
        )
        self.assertLess(
            sidebar_keys.index("smlouvy_ozo"),
            sidebar_keys.index("sprava_dat"),
        )
        self.assertLess(
            sidebar_keys.index("sprava_dat"),
            sidebar_keys.index("nastaveni"),
        )

        window._sidebar_buttons[MODULE_KEY].click()
        self.assertIsInstance(window.current_page_widget(), TestyPage)
        self.assertIs(window.current_page_widget(), window._page_widgets[MODULE_KEY])
        window.close()


if __name__ == "__main__":
    unittest.main()
