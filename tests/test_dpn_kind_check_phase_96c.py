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
    from moduly.kniha_urazu.ui.tabs.tab_uraz import TabUraz


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
        tab = TabUraz()
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
        tab = TabUraz()
        accident = SimpleNamespace(
            id=1,
            druh_urazu=KIND_UP_TO_3,
            podezreni_trestny_cin="NE",
            accident_date=date(2026, 2, 1),
            accident_time="10:00",
            dpn_od=date(2026, 2, 1),
            dpn_do=date(2026, 2, 25),
            druh_zraneni="",
            zranena_cast_tela="",
            hromadny_uraz="NE",
            celkovy_pocet_zranenych=1,
            cinnost_pri_urazu="",
            misto_urazu="",
            popis_urazoveho_deje="",
        )
        tab.load_data(accident)

        self.assertFalse(tab.dpn_kind_warning_label.isHidden())
        self.assertEqual(tab.dpn_kind_warning_label.text(), DPN_KIND_MISMATCH_MESSAGE)

        dialog = AccidentDialog()
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_uraz_widget.dpn_od.set_date_value(date(2026, 2, 1))
        dialog.tab_uraz_widget.dpn_do.set_date_value(date(2026, 2, 25))
        dialog._refresh_dpn_kind_warning()
        self.assertFalse(dialog.tab_uraz_widget.dpn_kind_warning_label.isHidden())

    def test_save_is_not_blocked_when_dpn_length_unknown(self) -> None:
        """Prvotní zápis: délka DPN ještě není známá → uložení nesmí blokovat."""
        dialog = AccidentDialog()
        dialog.tab_uraz_widget.accident_date.set_date_iso(date(2026, 3, 1).isoformat())
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(date(2026, 3, 1))
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_uraz_widget.dpn_od.set_date_value(date(2026, 3, 1))
        # dpn_do prázdné = DPN stále trvá / délka neznámá
        dialog._refresh_dpn_kind_warning()
        self.assertTrue(dialog.tab_uraz_widget.dpn_kind_warning_label.isHidden())

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

    def test_save_is_blocked_when_known_dpn_mismatches_kind(self) -> None:
        dialog = AccidentDialog()
        dialog.tab_uraz_widget.accident_date.set_date_iso(date(2026, 3, 1).isoformat())
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(date(2026, 3, 1))
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_uraz_widget.dpn_od.set_date_value(date(2026, 3, 1))
        dialog.tab_uraz_widget.dpn_do.set_date_value(date(2026, 3, 25))
        dialog._refresh_dpn_kind_warning()
        self.assertFalse(dialog.tab_uraz_widget.dpn_kind_warning_label.isHidden())

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

        with patch("moduly.kniha_urazu.ui.accident_dialog.QMessageBox.warning") as mock_warning:
            with patch.object(QDialog, "accept", return_value=None) as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertTrue(mock_warning.called)


if __name__ == "__main__":
    unittest.main()
