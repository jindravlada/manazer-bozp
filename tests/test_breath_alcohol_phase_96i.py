"""Fáze 96i – doladění zadávání množství alkoholu (‰ mimo pole, potvrzení > 4)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QMessageBox

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
        is_extreme_breath_alcohol,
        normalize_breath_alcohol_storage,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_dalsi import TabDalsiUdaje


class AlcoholAmountPhase96iRefineTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_amount_visible_only_when_positive(self) -> None:
        tab = TabDalsiUdaje()
        tab.kontrola_alkohol_ano.setChecked(True)
        tab.vysledek_kontroly_alkohol_negativni.setChecked(True)
        self.assertTrue(tab.mnozstvi_alkohol_row.isHidden())

        tab.vysledek_kontroly_alkohol_pozitivni.setChecked(True)
        self.assertFalse(tab.mnozstvi_alkohol_row.isHidden())

    def test_unit_label_outside_editable_field(self) -> None:
        tab = TabDalsiUdaje()
        self.assertEqual(tab.mnozstvi_alkohol_unit.text(), "‰")
        self.assertNotIn("‰", tab.mnozstvi_alkohol.placeholderText())

        form = tab.findChild(QFormLayout)
        labels = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item is not None and item.widget() is not None:
                labels.append(item.widget().text())
        self.assertIn("Množství:", labels)
        self.assertNotIn("Množství v promile (‰):", labels)

        tab.mnozstvi_alkohol.setText("0,24")
        self.assertEqual(tab.mnozstvi_alkohol.text(), "0,24")
        self.assertEqual(tab.get_data()["mnozstvi_alkohol"], "0,24")

    def test_legacy_values_load_without_unit(self) -> None:
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
        self.assertEqual(breath_alcohol_for_display("0.35 ‰"), "0,35")
        self.assertEqual(normalize_breath_alcohol_storage("0,35 ‰"), "0,35")

    def test_extreme_threshold_helper(self) -> None:
        self.assertFalse(is_extreme_breath_alcohol("4"))
        self.assertFalse(is_extreme_breath_alcohol("4,00"))
        self.assertFalse(is_extreme_breath_alcohol("1,15"))
        self.assertTrue(is_extreme_breath_alcohol("4,01"))
        self.assertTrue(is_extreme_breath_alcohol("5"))

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

    def test_extreme_value_shows_confirmation_and_can_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog._validate_date_rules = MagicMock(return_value=True)
        dialog.tab_dalsi_widget.kontrola_alkohol_ano.setChecked(True)
        dialog.tab_dalsi_widget.vysledek_kontroly_alkohol_pozitivni.setChecked(True)
        dialog.tab_dalsi_widget.mnozstvi_alkohol.setText("4,50")

        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes) as mock_exec:
            dialog.accept()

        mock_exec.assert_called_once()
        self.assertEqual(dialog.result(), QMessageBox.DialogCode.Accepted)

    def test_extreme_value_rejected_keeps_dialog_open(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog._validate_date_rules = MagicMock(return_value=True)
        dialog.tab_dalsi_widget.kontrola_alkohol_ano.setChecked(True)
        dialog.tab_dalsi_widget.vysledek_kontroly_alkohol_pozitivni.setChecked(True)
        dialog.tab_dalsi_widget.mnozstvi_alkohol.setText("5")

        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
            dialog.accept()

        self.assertNotEqual(dialog.result(), QMessageBox.DialogCode.Accepted)

    def test_normal_value_skips_confirmation(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog._validate_date_rules = MagicMock(return_value=True)
        dialog.tab_dalsi_widget.kontrola_alkohol_ano.setChecked(True)
        dialog.tab_dalsi_widget.vysledek_kontroly_alkohol_pozitivni.setChecked(True)
        dialog.tab_dalsi_widget.mnozstvi_alkohol.setText("0,24")

        with patch.object(QMessageBox, "exec") as mock_exec:
            dialog.accept()

        mock_exec.assert_not_called()
        self.assertEqual(dialog.result(), QMessageBox.DialogCode.Accepted)


if __name__ == "__main__":
    unittest.main()
