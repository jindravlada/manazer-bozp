"""Fáze 96g – výchozí stav ohlášení pracovního úrazu není automaticky splněný."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QRadioButton

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_OO_OHLASENI,
        row_status,
    )
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog


class AccidentReportingDefaultPhase96gTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def _new_accident_dialog(self) -> SetreniDialog:
        accident = Accident(
            number="96g/2026",
            accident_date=date(2026, 7, 10),
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
        )
        accident.id = 9607
        with patch(
            "moduly.kniha_urazu.ui.setreni.setreni_dialog.investigation_service.get_or_create",
            return_value=None,
        ):
            return SetreniDialog(accident=accident)

    def _oo_row(self, dialog: SetreniDialog) -> dict:
        for row in dialog.admin_ohlaseni_rows:
            if row.get("key") == OBLIGATION_OO_OHLASENI:
                return row
            if "Odborová organizace" in row.get("nazev", "") and "ohlášení" in row.get("nazev", ""):
                return row
        self.fail("Ohlášení odborové organizaci nebylo nalezeno.")

    def test_new_accident_does_not_create_completed_oo_notification(self) -> None:
        dialog = self._new_accident_dialog()
        row = self._oo_row(dialog)
        state = row_status(dialog._admin_row_state_dict(row), date(2026, 7, 11))
        self.assertNotEqual(state, "done")
        self.assertIn(state, ("waiting", "overdue"))

        status_label = dialog._admin_status_label(row)
        self.assertNotIn("Odesláno", status_label.text())
        self.assertIn(status_label.text(), ("Nevyřízeno", "Po termínu", "Neohlášeno"))

    def test_notification_date_and_time_empty_by_default(self) -> None:
        dialog = self._new_accident_dialog()
        row = self._oo_row(dialog)

        self.assertIsNone(dialog._admin_date_value(row["datum"]))
        self.assertEqual(row["cas"].text().strip(), "")

    def test_notification_method_not_preselected(self) -> None:
        dialog = self._new_accident_dialog()
        row = self._oo_row(dialog)

        self.assertEqual(dialog._radio_choice_value(row["zpusob"]), "")

    def test_osobne_is_visible_but_disabled(self) -> None:
        dialog = self._new_accident_dialog()
        row = self._oo_row(dialog)

        osobne = None
        for button in row["zpusob"].findChildren(QRadioButton):
            if button.text() == "Osobně":
                osobne = button
                break

        self.assertIsNotNone(osobne)
        self.assertFalse(osobne.isHidden())
        self.assertFalse(osobne.isEnabled())

    def test_manual_fill_still_marks_as_done(self) -> None:
        dialog = self._new_accident_dialog()
        row = self._oo_row(dialog)

        dialog._set_date_widget(row["datum"], date(2026, 7, 11))
        row["cas"].setText("09:15")
        dialog._set_radio_choice(row["zpusob"], "E-mail")

        self.assertEqual(dialog._admin_date_value(row["datum"]), date(2026, 7, 11))
        self.assertEqual(row["cas"].text(), "09:15")
        self.assertEqual(dialog._radio_choice_value(row["zpusob"]), "E-mail")
        self.assertEqual(
            row_status(dialog._admin_row_state_dict(row), date(2026, 7, 11)),
            "done",
        )

        data = dialog._admin_rows_data([row])[0]
        self.assertEqual(data["datum"], "2026-07-11")
        self.assertEqual(data["cas"], "09:15")
        self.assertEqual(data["zpusob"], "E-mail")


if __name__ == "__main__":
    unittest.main()
