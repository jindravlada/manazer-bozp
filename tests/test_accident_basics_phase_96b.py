"""Fáze 96b – základní údaje nového úrazu (datum zápisu, CZ-NACE, situace, DPN)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.cz_nace_service import cz_nace_service
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import dpn_calendar_days
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_uraz import TabUraz
    from moduly.kniha_urazu.ui.tabs.tab_zapisovatel_zamestnavatel import (
        SITUACE_OPTIONS,
        TabZapisovatelZamestnavatel,
    )


class AccidentBasicsPhase96bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_new_accident_prefills_today_as_datum_zapisu(self) -> None:
        dialog = AccidentDialog()
        self.assertEqual(
            dialog.tab_podatel_widget.datum_zapisu.get_date(),
            date.today(),
        )

    def test_existing_accident_keeps_original_datum_zapisu(self) -> None:
        original = date(2024, 5, 17)
        accident = SimpleNamespace(
            id=1,
            datum_zapisu=original,
            podatel_jmeno="",
            podatel_email="",
            podatel_telefon="",
            podatel_pracovni_zarazeni="",
            vrchni_dozor="",
            dalsi_zamestnavatel_typ="",
            dalsi_zamestnavatel_nazev="",
            dalsi_zamestnavatel_ico="",
            dalsi_zamestnavatel_adresa="",
            dalsi_zamestnavatel_cinnost="",
            dalsi_zamestnavatel_poznamka="",
            jmeno_prijmeni="",
            pohlavi="",
            datum_narozeni=None,
            osobni_cislo="",
            statni_obcanstvi="Česko",
            adresa_pobytu="",
            adresa_dorucovani="",
            telefon_email="",
            zdravotni_pojistovna="",
            vztah_k_zamestnavateli="",
            den_vzniku_pravniho_vztahu=None,
            druh_vykonavane_prace="",
            dpn_od=None,
            dpn_do=None,
            accident_date=date(2024, 5, 10),
            year=2024,
            number="1/2024",
            workplace_id=None,
            description="",
            status="",
            investigation_started_at=None,
        )

        # AccidentDialog._load expects full accident; use tab load directly for focused check.
        tab = TabZapisovatelZamestnavatel()
        self.assertEqual(tab.datum_zapisu.get_date(), date.today())
        tab.load_data(accident)
        self.assertEqual(tab.datum_zapisu.get_date(), original)

    def test_cz_nace_shows_code_and_name_for_stored_code(self) -> None:
        tab = TabZapisovatelZamestnavatel()
        tab._set_cz_nace_value(tab.dalsi_zamestnavatel_cinnost, "49200")
        display = tab.dalsi_zamestnavatel_cinnost.value()
        expected = cz_nace_service.get_display("49200")

        self.assertEqual(display, expected)
        self.assertIn("–", display)
        self.assertGreater(len(display), 5)

    def test_situace_jine_not_offered_for_new_record(self) -> None:
        tab = TabZapisovatelZamestnavatel()
        items = [tab.dalsi_zamestnavatel_typ.itemText(i) for i in range(tab.dalsi_zamestnavatel_typ.count())]

        self.assertEqual(items, list(SITUACE_OPTIONS))
        self.assertNotIn("Jiné", items)

    def test_legacy_situace_jine_can_be_opened(self) -> None:
        tab = TabZapisovatelZamestnavatel()
        accident = SimpleNamespace(
            datum_zapisu=date(2024, 1, 1),
            podatel_jmeno="",
            podatel_email="",
            podatel_telefon="",
            podatel_pracovni_zarazeni="",
            vrchni_dozor="OIP",
            dalsi_zamestnavatel_typ="Jiné",
            dalsi_zamestnavatel_nazev="",
            dalsi_zamestnavatel_ico="",
            dalsi_zamestnavatel_adresa="",
            dalsi_zamestnavatel_cinnost="",
            dalsi_zamestnavatel_poznamka="",
        )
        tab.load_data(accident)

        self.assertEqual(tab.dalsi_zamestnavatel_typ.currentText(), "Jiné")
        items = [tab.dalsi_zamestnavatel_typ.itemText(i) for i in range(tab.dalsi_zamestnavatel_typ.count())]
        self.assertIn("Jiné", items)

    def test_dpn_duration_recalculates_inclusively(self) -> None:
        tab = TabUraz()
        self.assertIn("—", tab.dpn_duration_label.text())

        start = date(2026, 3, 1)
        end = date(2026, 3, 3)
        tab.dpn_od.set_date_value(start)
        tab.dpn_do.set_date_value(end)

        self.assertEqual(dpn_calendar_days(start, end), 3)
        self.assertIn("3 dní", tab.dpn_duration_label.text())

        tab.dpn_do.clear_date()
        self.assertIn("—", tab.dpn_duration_label.text())

        tab.dpn_do.set_date_value(start + timedelta(days=4))
        self.assertIn("5 dní", tab.dpn_duration_label.text())


if __name__ == "__main__":
    unittest.main()
