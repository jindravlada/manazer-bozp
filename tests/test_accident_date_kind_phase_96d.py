"""Fáze 96d – kontroly data a druhu pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        ACCIDENT_DATE_DELAY_WARNING,
        ACCIDENT_DATE_FUTURE_MESSAGE,
        FATAL_KIND_INFO,
        INVESTIGATION_BEFORE_ACCIDENT_WARNING,
        RECORD_DATE_BEFORE_ACCIDENT_MESSAGE,
        SERIOUS_KIND_INFO,
        accident_kind_info_message,
        is_accident_date_delayed,
        is_accident_date_in_future,
        is_investigation_before_accident,
        is_record_date_before_accident,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_uraz import TabUraz


KIND_SERIOUS = "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)"
KIND_FATAL = "smrtelný"
KIND_PN = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


class AccidentDateKindPhase96dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def _bypass_required_validation(self, dialog: AccidentDialog) -> None:
        for tab in (
            dialog.tab_podatel_widget,
            dialog.tab_zamestnanec_widget,
            dialog.tab_uraz_widget,
            dialog.tab_pracoviste_widget,
            dialog.tab_dalsi_widget,
            dialog.tab_svedci_widget,
        ):
            if hasattr(tab, "validate"):
                tab.validate = MagicMock(return_value=[])

    def test_future_accident_date_blocks_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(
            (date.today() + timedelta(days=1)).isoformat()
        )
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(date.today())

        with patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(QDialog, "accept") as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertTrue(mock_warning.called)
        self.assertIn(ACCIDENT_DATE_FUTURE_MESSAGE, mock_warning.call_args.args[2])

    def test_accident_date_older_than_14_days_shows_warning(self) -> None:
        tab = TabUraz()
        old = date.today() - timedelta(days=15)
        tab.accident_date.set_date_iso(old.isoformat())

        self.assertTrue(is_accident_date_delayed(old))
        self.assertFalse(tab.accident_date_delay_warning.isHidden())
        self.assertEqual(tab.accident_date_delay_warning.text(), ACCIDENT_DATE_DELAY_WARNING)

        tab.accident_date.set_date_iso(date.today().isoformat())
        self.assertTrue(tab.accident_date_delay_warning.isHidden())

    def test_record_date_before_accident_blocks_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        accident_day = date.today() - timedelta(days=2)
        dialog.tab_uraz_widget.accident_date.set_date_iso(accident_day.isoformat())
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(accident_day - timedelta(days=1))

        with patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(QDialog, "accept") as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertIn(RECORD_DATE_BEFORE_ACCIDENT_MESSAGE, mock_warning.call_args.args[2])

    def test_investigation_before_accident_shows_warning(self) -> None:
        accident_day = date(2026, 3, 10)
        investigation_day = date(2026, 3, 8)
        self.assertTrue(is_investigation_before_accident(investigation_day, accident_day))
        self.assertFalse(is_investigation_before_accident(accident_day, accident_day))

        warning = INVESTIGATION_BEFORE_ACCIDENT_WARNING
        self.assertIn("zahájení šetření", warning)

    def test_serious_and_fatal_kind_info_lines(self) -> None:
        self.assertEqual(accident_kind_info_message(KIND_SERIOUS), SERIOUS_KIND_INFO)
        self.assertEqual(accident_kind_info_message(KIND_FATAL), FATAL_KIND_INFO)
        self.assertIsNone(accident_kind_info_message(KIND_PN))
        self.assertNotIn("ℹ", SERIOUS_KIND_INFO)
        self.assertNotIn("ℹ", FATAL_KIND_INFO)

    def test_fixing_values_clears_warnings(self) -> None:
        tab = TabUraz()
        tab.accident_date.set_date_iso((date.today() - timedelta(days=20)).isoformat())
        self.assertFalse(tab.accident_date_delay_warning.isHidden())
        tab.accident_date.set_date_iso((date.today() - timedelta(days=3)).isoformat())
        self.assertTrue(tab.accident_date_delay_warning.isHidden())
    def test_historical_record_can_be_opened_and_saved(self) -> None:
        old_day = date(2024, 6, 1)
        accident = SimpleNamespace(
            id=9,
            datum_zapisu=old_day,
            podatel_jmeno="Test",
            podatel_email="",
            podatel_telefon="",
            podatel_pracovni_zarazeni="",
            vrchni_dozor="OIP",
            dalsi_zamestnavatel_typ="",
            dalsi_zamestnavatel_nazev="",
            dalsi_zamestnavatel_ico="",
            dalsi_zamestnavatel_adresa="",
            dalsi_zamestnavatel_cinnost="",
            dalsi_zamestnavatel_poznamka="",
            jmeno_prijmeni="Jan",
            pohlavi="Muž",
            datum_narozeni=date(1990, 1, 1),
            osobni_cislo="",
            statni_obcanstvi="Česko",
            adresa_pobytu="Praha",
            adresa_dorucovani="",
            telefon_email="",
            zdravotni_pojistovna="111",
            vztah_k_zamestnavateli="zaměstnanec",
            den_vzniku_pravniho_vztahu=date(2020, 1, 1),
            druh_vykonavane_prace="x",
            dpn_od=None,
            dpn_do=None,
            druh_urazu=KIND_PN,
            podezreni_trestny_cin="NE",
            accident_date=old_day,
            accident_time="10:00",
            druh_zraneni="x",
            zranena_cast_tela="x",
            hromadny_uraz="NE",
            celkovy_pocet_zranenych=1,
            cinnost_pri_urazu="x",
            misto_urazu="hala",
            popis_urazoveho_deje="pád",
            kontrola_alkohol="NE",
            vysledek_kontroly_alkohol="",
            mnozstvi_alkohol="",
            kontrola_alkohol_duvod_neprovedeni="",
            kontrola_navykove_latky="NE",
            vysledek_kontroly_navykove_latky="",
            navykove_latky_popis="",
            kontrola_navykove_latky_duvod_neprovedeni="",
            porusene_predpisy="x",
            opatreni="x",
            uraz_pracoviste_zamestnavatele="ANO",
            charakteristika_pracoviste="",
            zdroj_urazu="",
            pricina_urazu="",
            ekonomicka_cinnost_subjektu="",
            ekonomicka_cinnost_pracoviste="",
            okres_pracoviste="",
            adresa_pracoviste="",
            nazev_subjektu="",
            ico_subjektu="",
            svedek_1_jmeno="",
            svedek_1_adresa="",
            svedek_2_jmeno="",
            svedek_2_adresa="",
            podpis_zraneneho="",
            podpis_zamestnavatele="",
            year=2024,
            number="9/2024",
            workplace_id=None,
            description="",
            status="",
            investigation_started_at=None,
        )

        tab = TabUraz()
        tab.load_data(accident)
        self.assertFalse(tab.accident_date_delay_warning.isHidden())
        self.assertFalse(is_accident_date_in_future(old_day))
        self.assertFalse(is_record_date_before_accident(old_day, old_day))

        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(old_day.isoformat())
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(old_day)

        with patch.object(QDialog, "accept") as mock_accept:
            with patch.object(QMessageBox, "warning") as mock_warning:
                dialog.accept()

        mock_warning.assert_not_called()
        mock_accept.assert_called_once()


if __name__ == "__main__":
    unittest.main()
