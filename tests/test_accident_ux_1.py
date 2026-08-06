"""ACCIDENT-UX-1: přesun akcí Ohlášení do přehledu úrazů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMenu, QToolButton

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
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage
    from moduly.kniha_urazu.ui.union_notice_dialog import UnionNoticeDialog


class AccidentUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_accident(self):
        return accident_service.create_accident(
            jmeno_prijmeni="Jan Novák",
            pohlavi="Muž",
            datum_narozeni=date(1990, 1, 1),
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            accident_date=date(2026, 4, 1),
            accident_time="10:00",
            popis_urazoveho_deje="Pád",
        )

    def test_notice_button_inactive_without_selection(self) -> None:
        self._create_accident()
        page = KnihaUrazuPage()
        self.assertEqual(page.notice_btn.text(), "Ohláška OO")
        self.assertFalse(page.notice_btn.isEnabled())
        self.assertFalse(hasattr(page, "union_notice_action"))

    def test_notice_button_active_with_selection(self) -> None:
        accident = self._create_accident()
        page = KnihaUrazuPage()
        self.assertTrue(page._select_accident(accident.id))
        page._refresh_action_buttons()
        self.assertTrue(page.notice_btn.isEnabled())

    def test_opens_same_union_notice_dialog(self) -> None:
        accident = self._create_accident()
        page = KnihaUrazuPage()
        page._select_accident(accident.id)

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
            page.open_union_notice()

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].id, accident.id)

    def test_editor_has_no_notice_menu(self) -> None:
        accident = self._create_accident()
        dialog = AccidentDialog(accident=accident)
        self.assertFalse(hasattr(dialog, "notice_btn"))
        self.assertFalse(hasattr(dialog, "union_notice_action"))
        self.assertFalse(hasattr(dialog, "open_union_notice"))
        for button in dialog.findChildren(QToolButton):
            self.assertNotEqual(button.text(), "Ohlášení")
        for menu in dialog.findChildren(QMenu):
            for action in menu.actions():
                self.assertNotIn("Odborová organizace", action.text())


if __name__ == "__main__":
    unittest.main()
