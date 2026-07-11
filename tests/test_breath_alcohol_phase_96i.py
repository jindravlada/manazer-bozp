"""Fáze 96i – zadávání výsledku dechové zkoušky bez znaku ‰."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.sluzby.breath_alcohol import (
        breath_alcohol_for_display,
        format_breath_alcohol_for_export,
        normalize_breath_alcohol_storage,
        sanitize_breath_alcohol_input,
    )
    from moduly.kniha_urazu.sluzby.vypis_urazu_service import vypis_urazu_service
    from moduly.kniha_urazu.ui.tabs.tab_dalsi import TabDalsiUdaje


class BreathAlcoholPhase96iTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_helpers_normalize_values(self) -> None:
        self.assertEqual(sanitize_breath_alcohol_input("0"), "0")
        self.assertEqual(sanitize_breath_alcohol_input("0,24"), "0,24")
        self.assertEqual(sanitize_breath_alcohol_input("1.15"), "1,15")
        self.assertEqual(sanitize_breath_alcohol_input("0,35 ‰"), "0,35")
        self.assertEqual(sanitize_breath_alcohol_input("abc1.2x"), "1,2")
        self.assertEqual(normalize_breath_alcohol_storage("0,24 ‰"), "0,24")
        self.assertEqual(normalize_breath_alcohol_storage(""), "")
        self.assertEqual(breath_alcohol_for_display("0.35 ‰"), "0,35")
        self.assertEqual(format_breath_alcohol_for_export("0,35"), "0,35 ‰")
        self.assertEqual(format_breath_alcohol_for_export(""), "")

    def test_ui_accepts_zero_and_decimal(self) -> None:
        tab = TabDalsiUdaje()
        tab.kontrola_alkohol_ano.setChecked(True)
        tab.vysledek_kontroly_alkohol_pozitivni.setChecked(True)

        tab.mnozstvi_alkohol.setText("0")
        self.assertEqual(tab.mnozstvi_alkohol.text(), "0")
        self.assertEqual(tab.get_data()["mnozstvi_alkohol"], "0")

        tab.mnozstvi_alkohol.setText("0,24")
        self.assertEqual(tab.mnozstvi_alkohol.text(), "0,24")
        self.assertEqual(tab.get_data()["mnozstvi_alkohol"], "0,24")

    def test_ui_converts_dot_to_comma(self) -> None:
        tab = TabDalsiUdaje()
        tab.mnozstvi_alkohol.setText("1.15")
        self.assertEqual(tab.mnozstvi_alkohol.text(), "1,15")
        self.assertEqual(tab.get_data()["mnozstvi_alkohol"], "1,15")

    def test_loads_legacy_value_without_unit(self) -> None:
        tab = TabDalsiUdaje()
        accident = SimpleNamespace(
            kontrola_alkohol="ANO",
            kontrola_alkohol_duvod_neprovedeni="",
            vysledek_kontroly_alkohol="Pozitivní",
            mnozstvi_alkohol="0,35 ‰",
            kontrola_navykove_latky="NE",
            kontrola_navykove_latky_duvod_neprovedeni="",
            vysledek_kontroly_navykove_latky="",
            navykove_latky_popis="",
            porusene_predpisy="",
            opatreni="",
        )
        tab.load_data(accident)
        self.assertEqual(tab.mnozstvi_alkohol.text(), "0,35")
        self.assertEqual(tab.mnozstvi_alkohol_unit.text(), "‰")
        self.assertEqual(tab.get_data()["mnozstvi_alkohol"], "0,35")
        self.assertNotIn("‰", tab.get_data()["mnozstvi_alkohol"])

    def test_loads_legacy_dot_value(self) -> None:
        tab = TabDalsiUdaje()
        accident = SimpleNamespace(
            kontrola_alkohol="ANO",
            kontrola_alkohol_duvod_neprovedeni="",
            vysledek_kontroly_alkohol="Pozitivní",
            mnozstvi_alkohol="0.35 ‰",
            kontrola_navykove_latky="NE",
            kontrola_navykove_latky_duvod_neprovedeni="",
            vysledek_kontroly_navykove_latky="",
            navykove_latky_popis="",
            porusene_predpisy="",
            opatreni="",
        )
        tab.load_data(accident)
        self.assertEqual(tab.mnozstvi_alkohol.text(), "0,35")

    def test_export_appends_unit(self) -> None:
        formatted = vypis_urazu_service._format_mnozstvi_alkohol("0,35")
        self.assertEqual(formatted, "0,35 ‰")
        self.assertEqual(vypis_urazu_service._format_mnozstvi_alkohol(""), "")

    def test_empty_value_works(self) -> None:
        tab = TabDalsiUdaje()
        tab.mnozstvi_alkohol.setText("")
        self.assertEqual(tab.get_data()["mnozstvi_alkohol"], "")
        labels = [label.text() for label in tab.findChildren(QLabel)]
        self.assertIn("‰", labels)


if __name__ == "__main__":
    unittest.main()
