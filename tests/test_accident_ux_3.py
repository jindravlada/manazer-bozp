"""ACCIDENT-UX-3: sjednocení aktivace tlačítek v přehledu úrazů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

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


class AccidentUx3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_accident(self, name: str = "Jan Novák"):
        return accident_service.create_accident(
            jmeno_prijmeni=name,
            pohlavi="Muž",
            datum_narozeni=date(1990, 1, 1),
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            accident_date=date(2026, 4, 1),
            accident_time="10:00",
            popis_urazoveho_deje="Pád",
        )

    def _selection_buttons(self, page: KnihaUrazuPage):
        return (
            page.edit_btn,
            page.notice_btn,
            page.investigation_btn,
            page.mu_investigation_btn,
            page.vypis_btn,
            page.final_report_btn,
        )

    def test_initial_state_only_new_enabled(self) -> None:
        self._create_accident()
        page = KnihaUrazuPage()
        self.assertTrue(page.new_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertFalse(button.isEnabled(), button.text())

    def test_one_selected_enables_record_actions(self) -> None:
        accident = self._create_accident()
        page = KnihaUrazuPage()
        self.assertTrue(page._select_accident(accident.id))
        page._refresh_action_buttons()
        self.assertTrue(page.new_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertTrue(button.isEnabled(), button.text())

    def test_clear_selection_disables_record_actions(self) -> None:
        accident = self._create_accident()
        page = KnihaUrazuPage()
        page._select_accident(accident.id)
        page._refresh_action_buttons()
        page.table.clearSelection()
        page.table.setCurrentCell(-1, -1)
        page._refresh_action_buttons()
        self.assertTrue(page.new_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertFalse(button.isEnabled(), button.text())

    def test_multi_selection_keeps_single_actions_disabled(self) -> None:
        first = self._create_accident("První")
        second = self._create_accident("Druhý")
        page = KnihaUrazuPage()
        # Tabulka má SingleSelection; simulujeme vícenásobný výběr přes mock.
        with patch.object(page, "_selected_row_count", return_value=2):
            page._refresh_action_buttons()
        self.assertTrue(page.new_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertFalse(button.isEnabled(), button.text())
        # Kontrola, že záznamy existují (aby se test neoptimalizoval pryč).
        self.assertIsNotNone(accident_service.get_by_id(first.id))
        self.assertIsNotNone(accident_service.get_by_id(second.id))


if __name__ == "__main__":
    unittest.main()
