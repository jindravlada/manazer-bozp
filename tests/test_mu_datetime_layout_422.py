"""Datum a čas stejné události na jednom řádku (Vyšetřování MU 4.2.2)."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

_TMP = Path(tempfile.mkdtemp(prefix="mu-datetime-layout-422-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.vysetrovani_mu.constants import SOURCE_TYPE_MANUAL
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service
    from moduly.vysetrovani_mu.ui.mu_chronologie_entry_dialog import MuChronologieEntryDialog
    from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog


class MuDatetimeLayout422TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _open(self, investigation=None) -> MuInvestigationDialog:
        dialog = MuInvestigationDialog(investigation=investigation)
        dialog.resize(640, 760)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def _show_tab(self, dialog: MuInvestigationDialog, widget) -> None:
        dialog.tabs.setCurrentWidget(widget)
        self.app.processEvents()

    def _assert_beside(self, left, right) -> None:
        self.app.processEvents()
        origin = left.window()
        left_pos = left.mapTo(origin, left.rect().center())
        right_pos = right.mapTo(origin, right.rect().center())
        self.assertGreater(left.width(), 40)
        self.assertGreater(right.width(), 40)
        if hasattr(left, "line_edit"):
            self.assertGreaterEqual(left.line_edit.width(), 90)
        self.assertLess(abs(left_pos.y() - right_pos.y()), 12)
        self.assertGreater(right_pos.x(), left_pos.x())
        self.assertIs(left.parentWidget(), right.parentWidget())

    def _labels(self, root) -> set[str]:
        return {label.text() for label in root.findChildren(QLabel)}

    def test_pairs_stay_on_one_row_in_a_narrow_window(self) -> None:
        dialog = self._open()
        try:
            self._show_tab(dialog, dialog.oznameni_widget)
            notice = dialog.oznameni_widget
            self._assert_beside(notice.oznameni_datum, notice.oznameni_cas)
            self._assert_beside(notice.oznameni_bozp_datum, notice.oznameni_bozp_cas)
            self.assertIn("Oznámení události:", self._labels(notice))
            self.assertIn("Oznámení BOZP:", self._labels(notice))
            self.assertGreaterEqual(notice.oznameni_cas.width(), 88)

            self._show_tab(dialog, dialog.zajisteni_dukazu_widget)
            evidence = dialog.zajisteni_dukazu_widget
            self._assert_beside(evidence.dukazy_datum, evidence.dukazy_cas)
            self._assert_beside(evidence.dukazy_datum_fotek, evidence.dukazy_cas_fotek)
            self._assert_beside(evidence.dukazy_dochazka_datum, evidence.dukazy_dochazka_cas)
            labels = self._labels(evidence)
            self.assertIn("Provedení zajištění:", labels)
            self.assertIn("Pořízení fotek / videa:", labels)
            self.assertIn("Nástup na směnu:", labels)

            rules = dialog.dodrzovani_predpisu_widget
            self._show_tab(dialog, rules)
            rules.inner_tabs.setCurrentIndex(1)
            self.app.processEvents()
            self._assert_beside(rules.dodrz_lekar_datum, rules.dodrz_lekar_platnost)
            typ_bottom = rules.dodrz_lekar_typ.mapTo(
                rules.dodrz_lekar_typ.window(), rules.dodrz_lekar_typ.rect().bottomLeft()
            )
            date_top = rules.dodrz_lekar_datum.mapTo(
                rules.dodrz_lekar_datum.window(), rules.dodrz_lekar_datum.rect().topLeft()
            )
            self.assertLess(typ_bottom.y(), date_top.y())
            self.assertIn("Typ prohlídky:", self._labels(rules))
            self.assertIn("Datum prohlídky", self._labels(rules))
            self.assertIn("Platnost do", self._labels(rules))

            self._show_tab(dialog, dialog.tabs.widget(0))
            self._assert_beside(dialog.event_date_edit, dialog.event_time_edit)
            self.assertIn("Vznik události:", self._labels(dialog))
        finally:
            self._close(dialog)

        milestone = MuChronologieEntryDialog()
        milestone.resize(420, 320)
        milestone.show()
        self.app.processEvents()
        try:
            self._assert_beside(milestone.datum_edit, milestone.cas_edit)
            self.assertGreaterEqual(milestone.cas_edit.width(), 88)
            self.assertIn("Datum", self._labels(milestone))
            self.assertIn("Čas", self._labels(milestone))
        finally:
            milestone.close()
            milestone.deleteLater()
            self.app.processEvents()

    def test_values_display_save_and_reload(self) -> None:
        dialog = self._open()
        try:
            dialog.title_edit.setText("Rozložení času")
            dialog._set_source_type(SOURCE_TYPE_MANUAL)
            dialog.event_date_edit.set_date_value(date(2026, 5, 2))
            dialog.event_time_edit.setText("8:15")

            notice = dialog.oznameni_widget
            notice.oznameni_datum.set_date_value(date(2026, 5, 2))
            notice.oznameni_cas.setText("8:20")
            notice.oznameni_bozp_datum.set_date_value(date(2026, 5, 3))
            notice.oznameni_bozp_cas.setText("")
            self.assertFalse(notice.oznameni_cas.blocks_save())
            notice.oznameni_cas.setText("14:60")
            self.assertTrue(notice.oznameni_cas.blocks_save())
            notice.oznameni_cas.setText("8:20")

            evidence = dialog.zajisteni_dukazu_widget
            evidence.dukazy_datum.set_date_value(date(2026, 5, 2))
            evidence.dukazy_cas.setText("9:00")
            evidence.dukazy_datum_fotek.set_date_value(date(2026, 5, 2))
            evidence.dukazy_cas_fotek.setText("9:05")
            evidence.dukazy_dochazka_datum.set_date_value(date(2026, 5, 2))
            evidence.dukazy_dochazka_cas.setText("6:30")

            rules = dialog.dodrzovani_predpisu_widget
            rules.dodrz_lekar_typ.setCurrentText("Vstupní")
            rules.dodrz_lekar_datum.set_date_value(date(2026, 4, 1))
            rules.dodrz_lekar_platnost.set_date_value(date(2028, 4, 1))

            milestone = MuChronologieEntryDialog()
            milestone.datum_edit.set_date_value(date(2026, 5, 2))
            milestone.cas_edit.setText("10:45")
            milestone.typ_edit.setText("Milník")
            milestone.popis_edit.setPlainText("Ruční záznam")
            entry = milestone.get_entry()
            milestone.deleteLater()
            entry["id"] = "layout-1"
            entry["source"] = "manual"
            dialog.casova_osa_widget._chronologie_entries.append(entry)

            self.assertTrue(dialog._persist())
            investigation_id = dialog.investigation.id
        finally:
            self._close(dialog)

        again = self._open(mu_investigation_service.get_by_id(investigation_id))
        try:
            self.assertEqual(again.event_date_edit.get_date(), date(2026, 5, 2))
            self.assertEqual(again.event_time_edit.text(), "08:15")
            notice = again.oznameni_widget
            self.assertEqual(notice.oznameni_datum.get_date(), date(2026, 5, 2))
            self.assertEqual(notice.oznameni_cas.text(), "08:20")
            self.assertEqual(notice.oznameni_bozp_datum.get_date(), date(2026, 5, 3))
            self.assertEqual(notice.oznameni_bozp_cas.text(), "")
            evidence = again.zajisteni_dukazu_widget
            self.assertEqual(evidence.dukazy_datum.get_date(), date(2026, 5, 2))
            self.assertEqual(evidence.dukazy_cas.text(), "09:00")
            self.assertEqual(evidence.dukazy_datum_fotek.get_date(), date(2026, 5, 2))
            self.assertEqual(evidence.dukazy_cas_fotek.text(), "09:05")
            self.assertEqual(evidence.dukazy_dochazka_datum.get_date(), date(2026, 5, 2))
            self.assertEqual(evidence.dukazy_dochazka_cas.text(), "06:30")
            rules = again.dodrzovani_predpisu_widget
            self.assertEqual(rules.dodrz_lekar_typ.currentText(), "Vstupní")
            self.assertEqual(rules.dodrz_lekar_datum.get_date(), date(2026, 4, 1))
            self.assertEqual(rules.dodrz_lekar_platnost.get_date(), date(2028, 4, 1))
            chronologie = json.loads(again.investigation.casova_osa_json)["chronologie"]
            self.assertEqual(chronologie[0]["datum"], "2026-05-02")
            self.assertEqual(chronologie[0]["cas"], "10:45")
            reloaded = MuChronologieEntryDialog(entry=chronologie[0])
            reloaded.show()
            self.app.processEvents()
            try:
                self.assertEqual(reloaded.datum_edit.get_date(), date(2026, 5, 2))
                self.assertEqual(reloaded.cas_edit.text(), "10:45")
                self._assert_beside(reloaded.datum_edit, reloaded.cas_edit)
            finally:
                reloaded.close()
                reloaded.deleteLater()
        finally:
            self._close(again)
