"""PU-DPN-2 – aktualizace ZoÚ po ukončení DPN."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.theme.status_colors import STATUS_DONE_BG, STATUS_WARNING_BG
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        DPN_RECORD_UPDATE_KEY,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_AKTUALIZACE_OO,
        OBLIGATION_AKTUALIZACE_POLICIE,
        OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
        OBLIGATION_AKTUALIZACE_ZP,
        OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
        OBLIGATION_OO_OHLASENI,
        POST_DPN_OBLIGATION_KEYS,
        applicable_obligations,
        dpn_record_update_from_saved_data,
        dpn_record_update_is_done,
        is_dpn_record_update_relevant,
        is_obligation_relevant,
        obligation_definitions_for_accident,
        obligation_rows_for_summary,
        obligations_summary_state,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.accident_table import AccidentTable
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
TODAY = date(2026, 4, 20)


class PuDpn2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(self, **overrides):
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": KIND_OVER_3,
            "accident_date": date(2026, 4, 1),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád",
            "dpn_od": date(2026, 4, 1),
            "dpn_do": None,
        }
        data.update(overrides)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            return accident_service.create_accident(**data)

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not str(raw).strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _done_rows(self, accident, saved_data=None) -> list[dict]:
        rows = []
        for item in applicable_obligations(accident, saved_data=saved_data):
            if item.key == OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN:
                continue
            if item.key in POST_DPN_OBLIGATION_KEYS:
                continue
            rows.append({"key": item.key, "datum": "2026-04-05"})
        return rows

    def _summary(self, accident, rows=None, saved_data=None):
        rows = rows if rows is not None else obligation_rows_for_summary(accident, saved_data)
        return obligations_summary_state(
            accident,
            rows,
            TODAY,
            saved_data=saved_data,
            union_organization_active=True,
        )

    def test_obligation_relevant_only_with_dpn_do_and_record(self) -> None:
        without_end = self._create()
        self.assertFalse(is_dpn_record_update_relevant(without_end))
        self.assertFalse(
            is_obligation_relevant(without_end, OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN)
        )

        with_end = accident_service.update_accident(
            without_end.id,
            dpn_do=date(2026, 4, 15),
        )
        self.assertTrue(is_dpn_record_update_relevant(with_end))
        keys = [item.key for item in applicable_obligations(with_end)]
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, keys)
        for key in (
            OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
            OBLIGATION_AKTUALIZACE_ZP,
            OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
            OBLIGATION_AKTUALIZACE_OO,
        ):
            self.assertEqual(keys.count(key), 1)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)

        short_pn = self._create(druh_urazu=KIND_UP_TO_3, dpn_do=date(2026, 4, 3))
        self.assertFalse(is_dpn_record_update_relevant(short_pn))

    def test_zou_turns_orange_after_dpn_do(self) -> None:
        accident = self._create()
        rows = self._done_rows(accident)
        self.assertEqual(self._summary(accident, rows), "done")

        table = AccidentTable()
        self.assertEqual(
            table._zou_color(accident, rows, TODAY).name(),
            STATUS_DONE_BG,
        )

        updated = accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 15))
        later_rows = self._done_rows(updated)
        self.assertEqual(self._summary(updated, later_rows), "waiting")
        self.assertEqual(
            table._zou_color(updated, later_rows, TODAY).name(),
            STATUS_WARNING_BG,
        )

    def test_reopen_and_dpn_do_change_do_not_duplicate(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        first_keys = [item.key for item in applicable_obligations(accident)]
        accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 18))
        reloaded = accident_service.get_by_id(accident.id)
        second_keys = [item.key for item in applicable_obligations(reloaded)]
        self.assertEqual(first_keys, second_keys)
        for key in (
            OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
            OBLIGATION_AKTUALIZACE_ZP,
            OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
            OBLIGATION_AKTUALIZACE_OO,
        ):
            self.assertEqual(first_keys.count(key), 1)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, first_keys)

        dialog = AccidentDialog(accident=reloaded)
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 4, 19))
        accident_service.update_accident(reloaded.id, **dialog.get_data())
        dialog.close()
        dialog = AccidentDialog(accident=accident_service.get_by_id(reloaded.id))
        accident_service.update_accident(reloaded.id, **dialog.get_data())
        dialog.close()

        current = accident_service.get_by_id(reloaded.id)
        current_keys = [item.key for item in applicable_obligations(current)]
        for key in (
            OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
            OBLIGATION_AKTUALIZACE_ZP,
            OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
            OBLIGATION_AKTUALIZACE_OO,
        ):
            self.assertEqual(current_keys.count(key), 1)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, current_keys)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, current_keys)
        self.assertNotIn(DPN_RECORD_UPDATE_KEY, self._saved_data(reloaded.id))

    def test_completing_update_returns_zou_to_green(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertTrue(tab.is_content_active())
        self.assertFalse(tab.portal_suip_done.isEnabled())
        self.assertFalse(tab.signed_record_done.isEnabled())
        tab.portal_suip_done.setChecked(True)
        tab.portal_suip_date.set_date_value(date(2026, 4, 16))
        tab.signed_record_done.setChecked(True)
        tab.signed_record_date.set_date_value(date(2026, 4, 17))
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = self._saved_data(accident.id)
        self.assertFalse(dpn_record_update_is_done(dpn_record_update_from_saved_data(saved)))
        reloaded = accident_service.get_by_id(accident.id)
        original_rows = self._done_rows(reloaded, saved)
        self.assertEqual(self._summary(reloaded, original_rows, saved), "waiting")

    def test_clearing_dpn_do_removes_unfulfilled_keeps_done(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        accident_service.update_accident(
            accident.id,
            dpn_do=None,
            dpn_record_update={
                "portal_suip_done": True,
                "portal_suip_date": "2026-04-16",
                "signed_record_done": False,
                "signed_record_date": None,
            },
        )
        self.assertFalse(
            is_obligation_relevant(
                accident_service.get_by_id(accident.id),
                OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
            )
        )
        self.assertNotIn(DPN_RECORD_UPDATE_KEY, self._saved_data(accident.id))

        done_accident = self._create(dpn_do=date(2026, 4, 15), jmeno_prijmeni="Hotovo")
        accident_service.update_accident(
            done_accident.id,
            dpn_record_update={
                "portal_suip_done": True,
                "portal_suip_date": "2026-04-16",
                "signed_record_done": True,
                "signed_record_date": "2026-04-17",
            },
        )
        accident_service.update_accident(done_accident.id, dpn_do=None)
        kept = self._saved_data(done_accident.id)
        self.assertTrue(dpn_record_update_is_done(dpn_record_update_from_saved_data(kept)))
        self.assertFalse(
            is_obligation_relevant(
                accident_service.get_by_id(done_accident.id),
                OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
            )
        )

    def test_old_accident_without_dpn_do_keeps_existing_zou(self) -> None:
        accident = self._create()
        rows = self._done_rows(accident)
        self.assertEqual(self._summary(accident, rows), "done")
        self.assertEqual(self._summary(accident, []), "waiting")
        self.assertNotIn(
            OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
            {item.key for item in applicable_obligations(accident)},
        )

    def test_setreni_dialog_does_not_add_full_recipient_row(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        defs = obligation_definitions_for_accident(accident, self._saved_data(accident.id))
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, {item.key for item in defs})
        dialog = SetreniDialog(accident=accident)
        keys = [
            row.get("key")
            for row in (
                dialog.admin_ohlaseni_rows
                + dialog.admin_zaznam_rows
                + dialog.admin_odeslani_rows
                + dialog.admin_predani_rows
                + getattr(dialog, "admin_dpn_rows", [])
            )
        ]
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, keys)
        dialog.close()

    def test_existing_union_only_zou_logic_unchanged(self) -> None:
        accident = self._create(druh_urazu=KIND_UP_TO_3, dpn_do=None)
        self.assertEqual(self._summary(accident, []), "waiting")
        done_rows = [{"key": OBLIGATION_OO_OHLASENI, "datum": "2026-04-02"}]
        self.assertEqual(self._summary(accident, done_rows), "done")

    def test_dialog_starts_unfulfilled_when_dpn_do_is_set(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 4, 15))
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertTrue(tab.is_content_active())
        self.assertFalse(tab.portal_suip_done.isChecked())
        self.assertFalse(tab.signed_record_done.isChecked())
        self.assertIsNone(tab.portal_suip_date.get_date())
        self.assertIsNone(tab.signed_record_date.get_date())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
