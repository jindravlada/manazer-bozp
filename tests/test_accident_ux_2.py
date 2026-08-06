"""ACCIDENT-UX-2: zjednodušení tlačítka Ohláška OO."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QToolButton

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

    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage
    from moduly.kniha_urazu.ui.union_notice_dialog import UnionNoticeDialog


class AccidentUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_accident(self):
        return accident_service.create_accident(
            jmeno_prijmeni="Petr Svoboda",
            pohlavi="Muž",
            datum_narozeni=date(1988, 5, 5),
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            accident_date=date(2026, 5, 1),
            accident_time="09:00",
            popis_urazoveho_deje="Pád ze schodů",
        )

    def test_plain_button_label_and_no_menu(self) -> None:
        page = KnihaUrazuPage()
        self.assertIsInstance(page.notice_btn, QPushButton)
        self.assertNotIsInstance(page.notice_btn, QToolButton)
        self.assertEqual(page.notice_btn.text(), "Ohláška OO")
        self.assertFalse(hasattr(page, "union_notice_action"))
        self.assertEqual(len(page.notice_btn.findChildren(QMenu)), 0)

    def test_click_opens_union_notice_directly(self) -> None:
        accident = self._create_accident()
        page = KnihaUrazuPage()
        page._select_accident(accident.id)
        page._refresh_notice_button()
        self.assertTrue(page.notice_btn.isEnabled())

        opened: list[object] = []

        class FakeDialog(UnionNoticeDialog):
            def __init__(self, parent=None, *, accident):
                opened.append(accident)
                super().__init__(parent, accident=accident)

            def exec(self):
                return 0

        with patch(
            "moduly.kniha_urazu.ui.kniha_urazu_page.UnionNoticeDialog",
            FakeDialog,
        ):
            page.notice_btn.click()

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].id, accident.id)


if __name__ == "__main__":
    unittest.main()
