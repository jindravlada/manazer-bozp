"""Fáze 96c – inteligentní kontrola délky pracovní neschopnosti vs. druh úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
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

    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        DPN_KIND_MISMATCH_MESSAGE,
        is_dpn_kind_mismatch,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_zamestnanec import TabZamestnanec


KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


class DpnKindCheckPhase96cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_helper_matching_combinations_are_ok(self) -> None:
        self.assertFalse(is_dpn_kind_mismatch(KIND_UP_TO_3, 1))
        self.assertFalse(is_dpn_kind_mismatch(KIND_UP_TO_3, 3))
        self.assertFalse(is_dpn_kind_mismatch(KIND_OVER_3, 4))
        self.assertFalse(is_dpn_kind_mismatch(KIND_OVER_3, 25))
        self.assertFalse(is_dpn_kind_mismatch("", 25))
        self.assertFalse(is_dpn_kind_mismatch(KIND_OVER_3, None))

    def test_helper_detects_mismatches(self) -> None:
        self.assertTrue(is_dpn_kind_mismatch(KIND_UP_TO_3, 25))
        self.assertTrue(is_dpn_kind_mismatch(KIND_OVER_3, 1))
        self.assertTrue(is_dpn_kind_mismatch(KIND_OVER_3, 3))

    def test_ui_shows_and_clears_warning(self) -> None:
        tab = TabZamestnanec()
        tab.dpn_od.set_date_value(date(2026, 1, 1))
        tab.dpn_do.set_date_value(date(2026, 1, 25))
        tab.refresh_dpn_kind_warning(KIND_UP_TO_3)

        self.assertFalse(tab.dpn_kind_warning_label.isHidden())
        self.assertEqual(tab.dpn_kind_warning_label.text(), DPN_KIND_MISMATCH_MESSAGE)

        tab.refresh_dpn_kind_warning(KIND_OVER_3)
        self.assertTrue(tab.dpn_kind_warning_label.isHidden())
        self.assertEqual(tab.dpn_kind_warning_label.text(), "")

        tab.refresh_dpn_kind_warning(KIND_OVER_3)
        tab.dpn_do.set_date_value(date(2026, 1, 2))
        self.assertFalse(tab.dpn_kind_warning_label.isHidden())

        tab.dpn_do.set_date_value(date(2026, 1, 10))
        self.assertTrue(tab.dpn_kind_warning_label.isHidden())

    def test_opening_existing_mismatched_record_shows_warning(self) -> None:
        tab = TabZamestnanec()
        accident = SimpleNamespace(
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
            dpn_od=date(2026, 2, 1),
            dpn_do=date(2026, 2, 25),
            druh_urazu=KIND_UP_TO_3,
        )
        tab.load_data(accident)

        self.assertFalse(tab.dpn_kind_warning_label.isHidden())
        self.assertEqual(tab.dpn_kind_warning_label.text(), DPN_KIND_MISMATCH_MESSAGE)

        dialog = AccidentDialog()
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date(2026, 2, 1))
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 2, 25))
        dialog._refresh_dpn_kind_warning()
        self.assertFalse(dialog.tab_zamestnanec_widget.dpn_kind_warning_label.isHidden())

    def test_save_is_not_blocked_by_warning(self) -> None:
        dialog = AccidentDialog()
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date(2026, 3, 1))
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 3, 25))
        dialog._refresh_dpn_kind_warning()
        self.assertFalse(dialog.tab_zamestnanec_widget.dpn_kind_warning_label.isHidden())

        # Bypass other required-field validation; ensure warning itself does not reject.
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

        with patch.object(QDialog, "accept", return_value=None) as mock_accept:
            dialog.accept()

        mock_accept.assert_called_once()


if __name__ == "__main__":
    unittest.main()
