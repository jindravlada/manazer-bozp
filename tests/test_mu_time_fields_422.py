"""Validace časů ve Vyšetřování MU (4.2.2)."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp(prefix="mu-time-fields-422-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session

    initialize_database()

    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service
    from moduly.vysetrovani_mu.ui.mu_chronologie_entry_dialog import MuChronologieEntryDialog
    from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog
    from moduly.vysetrovani_mu.ui.mu_time_edit import (
        PRECISION_HHMM,
        PRECISION_HHMMSS,
        canonical_time,
        clock_for_instant,
        display_stored_time,
    )


class MuTimeText422TestCase(unittest.TestCase):
    def test_regular_time_accepts_only_complete_clock(self) -> None:
        self.assertEqual(canonical_time("14:35", PRECISION_HHMM), "14:35")
        self.assertEqual(canonical_time("8:05", PRECISION_HHMM), "08:05")
        self.assertEqual(canonical_time("14.35", PRECISION_HHMM), "14:35")
        self.assertEqual(canonical_time("14:35:00", PRECISION_HHMM), "14:35")
        self.assertEqual(canonical_time("", PRECISION_HHMM), None)
        self.assertIsNone(canonical_time("14", PRECISION_HHMM))
        self.assertIsNone(canonical_time("14:5", PRECISION_HHMM))
        self.assertIsNone(canonical_time("24:00", PRECISION_HHMM))
        self.assertIsNone(canonical_time("14:60", PRECISION_HHMM))
        self.assertIsNone(canonical_time("14:35:07", PRECISION_HHMM))
        self.assertIsNone(canonical_time("cca 14:30", PRECISION_HHMM))

    def test_device_time_requires_seconds_and_does_not_invent_them(self) -> None:
        self.assertEqual(canonical_time("14:35:07", PRECISION_HHMMSS), "14:35:07")
        self.assertEqual(canonical_time("14.35.00", PRECISION_HHMMSS), "14:35:00")
        self.assertEqual(canonical_time("", PRECISION_HHMMSS), None)
        self.assertIsNone(canonical_time("14:35", PRECISION_HHMMSS))
        self.assertIsNone(canonical_time("14:35:60", PRECISION_HHMMSS))
        self.assertEqual(clock_for_instant("14"), "")
        self.assertEqual(clock_for_instant("14:35"), "14:35")
        self.assertEqual(clock_for_instant("14:35:07"), "14:35:07")
        self.assertEqual(display_stored_time("14:35", PRECISION_HHMMSS), ("14:35", True))
        self.assertEqual(display_stored_time("14:35:07", PRECISION_HHMM), ("14:35:07", True))
        self.assertEqual(display_stored_time("14.35", PRECISION_HHMM), ("14:35", False))
        self.assertEqual(display_stored_time("14:35:00", PRECISION_HHMM), ("14:35", False))


class MuTimeFields422TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _open(self, investigation=None) -> MuInvestigationDialog:
        dialog = MuInvestigationDialog(investigation=investigation)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: MuInvestigationDialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def _raw(self, investigation_id: int, column: str):
        with get_session() as session:
            return session.execute(
                text(f"SELECT {column} FROM mu_investigations WHERE id = :id"),
                {"id": investigation_id},
            ).scalar()

    def _legacy(self):
        casova_osa = {
            "cas_synchronizace": {
                "caszarizeni_srovnani_cas": "14:35:00",
                "caszarizeni_visible_rows": 2,
                "caszarizeni_rows": [
                    {
                        "zarizeni": "kamera",
                        "cas_zarizeni": "14:35:10",
                        "cas_mobil": "14:35:00",
                        "rozdil": "+00:00:00",
                        "srovnany_cas": "14:35:00",
                        "foto": "",
                    },
                    {
                        "zarizeni": "hodiny",
                        "cas_zarizeni": "14:35",
                        "cas_mobil": "14:35:01",
                        "rozdil": "historicky",
                        "srovnany_cas": "historicky",
                        "foto": "",
                    },
                ],
            },
            "chronologie": [
                {
                    "id": "h1",
                    "datum": "2026-04-01",
                    "cas": "14.40",
                    "typ": "Milník",
                    "popis": "původní",
                    "source": "manual",
                }
            ],
        }
        return mu_investigation_service.create_investigation(
            title="Starý spis",
            started_at=date(2026, 4, 1),
            event_date=date(2026, 4, 1),
            event_time="14:35:07",
            oznameni_cas="14.35",
            oznameni_bozp_cas="cca 14:30",
            ohledani_mista_json=json.dumps(
                {"ohledani_zahajeni": "14:35:00", "ohledani_ukonceni": "kolem poledne"}
            ),
            zajisteni_dukazu_json=json.dumps({"cas": "9:05", "cas_fotek": "25:99", "dochazka_cas": ""}),
            casova_osa_json=json.dumps(casova_osa),
        )

    def test_invalid_time_is_not_saved_and_empty_time_is_saved(self) -> None:
        dialog = self._open()
        try:
            dialog.title_edit.setText("Nový čas")
            dialog._set_source_type("manual")
            dialog.event_date_edit.set_date_value(date(2026, 5, 2))
            dialog.event_time_edit.setText("14:60")
            self.assertTrue(dialog.event_time_edit.blocks_save())
            with patch("moduly.vysetrovani_mu.ui.mu_investigation_dialog.QMessageBox.warning"):
                self.assertFalse(dialog._persist())
            self.assertIsNone(dialog.investigation)
            dialog.event_time_edit.setText("")
            self.assertFalse(dialog.event_time_edit.blocks_save())
            dialog.event_time_edit.setText("8:05")
            self.assertTrue(dialog._persist())
            investigation_id = dialog.investigation.id
        finally:
            self._close(dialog)

        stored = mu_investigation_service.get_by_id(investigation_id)
        self.assertEqual(stored.event_date, date(2026, 5, 2))
        self.assertEqual(stored.event_time, "08:05")

    def test_opening_legacy_record_does_not_write_and_save_keeps_history(self) -> None:
        created = self._legacy()
        before_event = self._raw(created.id, "event_time")
        before_notice = self._raw(created.id, "oznameni_cas")
        before_json = self._raw(created.id, "casova_osa_json")

        dialog = self._open(mu_investigation_service.get_by_id(created.id))
        try:
            self.assertEqual(dialog.event_time_edit.text(), "14:35:07")
            self.assertTrue(dialog.event_time_edit._preserved)
            self.assertEqual(dialog.oznameni_widget.oznameni_cas.text(), "14:35")
            self.assertEqual(dialog.oznameni_widget.oznameni_bozp_cas.text(), "cca 14:30")
            self.assertEqual(dialog.ohledani_mista_widget.ohledani_zahajeni.text(), "14:35")
            self.assertEqual(dialog.ohledani_mista_widget.ohledani_ukonceni.text(), "kolem poledne")
            self.assertEqual(dialog.zajisteni_dukazu_widget.dukazy_cas.text(), "09:05")
            self.assertEqual(dialog.zajisteni_dukazu_widget.dukazy_cas_fotek.text(), "25:99")
            axis = dialog.casova_osa_widget
            self.assertEqual(axis.caszarizeni_1_rozdil.text(), "+00:00:10")
            self.assertEqual(axis.caszarizeni_2_cas_zarizeni.text(), "14:35")
            self.assertEqual(axis.caszarizeni_2_rozdil.text(), "")
            self.assertNotIn("00:00:00", axis.caszarizeni_2_rozdil.text())
            self.assertEqual(
                dialog.casova_osa_widget._reference_event_datetime(),
                datetime(2026, 4, 1, 14, 35, 7),
            )
            self.assertFalse(dialog._is_dirty())
            dialog.reject()
        finally:
            self._close(dialog)

        self.assertEqual(self._raw(created.id, "event_time"), before_event)
        self.assertEqual(self._raw(created.id, "oznameni_cas"), before_notice)
        self.assertEqual(self._raw(created.id, "casova_osa_json"), before_json)

        again = self._open(mu_investigation_service.get_by_id(created.id))
        try:
            again.title_edit.setText("Starý spis upravený")
            again.event_time_edit.setText("14:36:08")
            self.assertTrue(again.event_time_edit.blocks_save())
            with patch("moduly.vysetrovani_mu.ui.mu_investigation_dialog.QMessageBox.warning"):
                self.assertFalse(again._persist())
            again.event_time_edit.set_stored_text("14:35:07")
            self.assertTrue(again._persist())
        finally:
            self._close(again)

        stored = mu_investigation_service.get_by_id(created.id)
        self.assertEqual(stored.event_date, date(2026, 4, 1))
        self.assertEqual(stored.event_time, "14:35:07")
        self.assertEqual(stored.oznameni_cas, "14:35")
        self.assertEqual(stored.oznameni_bozp_cas, "cca 14:30")
        ohledani = json.loads(stored.ohledani_mista_json)
        self.assertEqual(ohledani["ohledani_zahajeni"], "14:35")
        self.assertEqual(ohledani["ohledani_ukonceni"], "kolem poledne")
        zajisteni = json.loads(stored.zajisteni_dukazu_json)
        self.assertEqual(zajisteni["cas"], "09:05")
        self.assertEqual(zajisteni["cas_fotek"], "25:99")
        casova = json.loads(stored.casova_osa_json)
        rows = casova["cas_synchronizace"]["caszarizeni_rows"]
        self.assertEqual(rows[0]["cas_zarizeni"], "14:35:10")
        self.assertEqual(rows[0]["rozdil"], "+00:00:10")
        self.assertEqual(rows[1]["cas_zarizeni"], "14:35")
        self.assertEqual(rows[1]["rozdil"], "")
        self.assertEqual(casova["chronologie"][0]["cas"], "14.40")

    def test_chronologie_keeps_unread_text_until_the_time_is_edited(self) -> None:
        kept = MuChronologieEntryDialog(
            entry={"datum": "2026-04-01", "cas": "cca 9", "typ": "Milník", "popis": "původní"}
        )
        kept.popis_edit.setPlainText("upravený popis")
        self.assertFalse(kept.cas_edit.blocks_save())
        self.assertEqual(kept.get_entry()["cas"], "cca 9")
        kept.deleteLater()

        changed = MuChronologieEntryDialog(entry={"datum": "2026-04-01", "cas": "cca 9", "typ": "", "popis": ""})
        changed.cas_edit.setText("14:60")
        self.assertTrue(changed.cas_edit.blocks_save())
        changed.cas_edit.setText("7:01")
        self.assertFalse(changed.cas_edit.blocks_save())
        self.assertEqual(changed.get_entry()["cas"], "07:01")
        changed.deleteLater()
