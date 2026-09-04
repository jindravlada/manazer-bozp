"""PU-DPN-3 – konkrétní ohlašovací povinnosti po ukončení DPN."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QRadioButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-3-"))

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
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_AKTUALIZACE_OO,
        OBLIGATION_AKTUALIZACE_POLICIE,
        OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
        OBLIGATION_AKTUALIZACE_ZP,
        OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
        OBLIGATION_EZOP,
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_OO_PREDANI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_ZAMESTNANEC_PREDANI,
        OBLIGATION_ZP_ZASLANI,
        POST_DPN_OBLIGATION_KEYS,
        applicable_obligations,
        dpn_record_update_overview_from_saved_data,
        is_obligation_relevant,
        obligation_default_deadline,
        obligation_rows_for_summary,
        obligations_summary_state,
        row_is_done,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.accident_table import AccidentTable
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import OVERVIEW_SOURCE_HINT
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
KIND_SERIOUS = "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)"
KIND_FATAL = "smrtelný"
TODAY = date(2026, 4, 20)
COMMON_POST_DPN = {
    OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
    OBLIGATION_AKTUALIZACE_ZP,
    OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
    OBLIGATION_AKTUALIZACE_OO,
}


class PuDpn3TestCase(unittest.TestCase):
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
            "vrchni_dozor": "OIP",
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

    def _write_saved(self, accident_id: int, payload: dict) -> dict:
        current = self._saved_data(accident_id)
        current.update(payload)
        investigation_service.save_zajisteni_dukazu(
            accident_id,
            json.dumps(current, ensure_ascii=False),
        )
        return self._saved_data(accident_id)

    def _keys(self, accident, saved_data=None, *, union_active=True) -> set[str]:
        return {
            item.key
            for item in applicable_obligations(
                accident,
                saved_data=saved_data,
                union_organization_active=union_active,
            )
        }

    def _post_dpn_keys(self, accident, saved_data=None, *, union_active=True) -> set[str]:
        return self._keys(accident, saved_data, union_active=union_active) & POST_DPN_OBLIGATION_KEYS

    def _done_original_rows(self, accident, saved_data=None) -> list[dict]:
        return [
            {"key": item.key, "datum": "2026-04-05"}
            for item in applicable_obligations(accident, saved_data=saved_data)
            if item.key not in POST_DPN_OBLIGATION_KEYS
        ]

    def _done_all_rows(self, accident, saved_data=None) -> list[dict]:
        return [
            {"key": item.key, "datum": "2026-04-16"}
            for item in applicable_obligations(accident, saved_data=saved_data)
        ]

    def _summary(self, accident, rows, saved_data=None, *, union_active=True):
        return obligations_summary_state(
            accident,
            rows,
            TODAY,
            saved_data=saved_data,
            union_organization_active=union_active,
        )

    def _admin_keys(self, dialog: SetreniDialog) -> list[str]:
        rows = (
            list(dialog.admin_ohlaseni_rows)
            + list(dialog.admin_zaznam_rows)
            + list(dialog.admin_odeslani_rows)
            + list(dialog.admin_predani_rows)
            + list(getattr(dialog, "admin_dpn_rows", []))
        )
        return [row.get("key") for row in rows]

    def _visible_dpn_keys(self, dialog: SetreniDialog) -> list[str]:
        return [
            row.get("key")
            for row in getattr(dialog, "admin_dpn_rows", [])
            if dialog._admin_row_relevant(row)
        ]

    def _row_by_key(self, dialog: SetreniDialog, key: str) -> dict:
        for row in getattr(dialog, "admin_dpn_rows", []):
            if row.get("key") == key:
                return row
        self.fail(f"Povinnost {key} nebyla nalezena.")

    def test_ordinary_accident_creates_post_dpn_recipients(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        keys = self._post_dpn_keys(accident)
        self.assertEqual(keys, COMMON_POST_DPN)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, self._keys(accident))
        self.assertFalse(
            is_obligation_relevant(accident, OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN)
        )

    def test_oip_and_obu_use_same_portal_update_key(self) -> None:
        oip = self._create(dpn_do=date(2026, 4, 15), vrchni_dozor="OIP", jmeno_prijmeni="OIP")
        obu = self._create(dpn_do=date(2026, 4, 15), vrchni_dozor="OBÚ", jmeno_prijmeni="OBÚ")
        self.assertEqual(self._post_dpn_keys(oip), COMMON_POST_DPN)
        self.assertEqual(self._post_dpn_keys(obu), COMMON_POST_DPN)
        self.assertEqual(oip.vrchni_dozor, "OIP")
        self.assertEqual(obu.vrchni_dozor, "OBÚ")

    def test_irrelevant_recipients_are_not_created(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        keys = self._keys(accident)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)
        self.assertNotIn("aktualizace_zakonna_pojistovna", keys)
        self.assertNotIn("Kooperativa", keys)
        labels = {item.label for item in applicable_obligations(accident)}
        self.assertFalse(any("zákonn" in label.lower() for label in labels))
        self.assertFalse(any(label.startswith("EZOP") and "aktualiz" in label.lower() for label in labels))

        without_union = self._post_dpn_keys(accident, union_active=False)
        self.assertEqual(
            without_union,
            {
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                OBLIGATION_AKTUALIZACE_ZP,
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
            },
        )
        self.assertNotIn(OBLIGATION_AKTUALIZACE_OO, without_union)

        with_police = self._create(
            dpn_do=date(2026, 4, 15),
            podezreni_trestny_cin="ANO",
            jmeno_prijmeni="S TČ",
        )
        self.assertIn(OBLIGATION_AKTUALIZACE_POLICIE, self._post_dpn_keys(with_police))
        self.assertTrue(is_obligation_relevant(with_police, OBLIGATION_POLICIE_ZASLANI))

        fatal = self._create(
            dpn_do=date(2026, 4, 15),
            druh_urazu=KIND_FATAL,
            jmeno_prijmeni="Smrtelný",
        )
        fatal_keys = self._post_dpn_keys(fatal)
        self.assertIn(OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL, fatal_keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_ZP, fatal_keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_OO, fatal_keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_POLICIE, fatal_keys)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAMESTNANEC, fatal_keys)
        self.assertFalse(is_obligation_relevant(fatal, OBLIGATION_ZAMESTNANEC_PREDANI))

    def test_zou_green_then_orange_then_green(self) -> None:
        accident = self._create()
        original = self._done_original_rows(accident)
        self.assertEqual(self._summary(accident, original), "done")
        table = AccidentTable()
        self.assertEqual(
            table._zou_color(accident, original, TODAY).name(),
            STATUS_DONE_BG,
        )

        updated = accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 15))
        original_after = self._done_original_rows(updated)
        self.assertEqual(self._summary(updated, original_after), "waiting")
        self.assertEqual(
            table._zou_color(updated, original_after, TODAY).name(),
            STATUS_WARNING_BG,
        )

        all_done = self._done_all_rows(updated)
        self.assertEqual(self._summary(updated, all_done), "done")
        self.assertEqual(
            table._zou_color(updated, all_done, TODAY).name(),
            STATUS_DONE_BG,
        )

    def test_no_duplicates_on_reopen_or_date_change(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        first = self._keys(accident)
        accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 18))
        second = self._keys(accident_service.get_by_id(accident.id))
        self.assertEqual(first, second)
        first_list = [
            item.key for item in applicable_obligations(accident_service.get_by_id(accident.id))
        ]
        for key in COMMON_POST_DPN:
            self.assertEqual(first_list.count(key), 1)

        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        visible = self._visible_dpn_keys(dialog)
        self.assertEqual(set(visible), COMMON_POST_DPN)
        self.assertEqual(len(visible), len(COMMON_POST_DPN))
        dialog.accept()
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        again = self._visible_dpn_keys(dialog)
        self.assertEqual(again, visible)
        saved_rows = self._saved_data(accident.id).get("admin_zaslani") or []
        post_dpn_saved = [
            row.get("key") for row in saved_rows if row.get("key") in POST_DPN_OBLIGATION_KEYS
        ]
        self.assertEqual(len(post_dpn_saved), len(set(post_dpn_saved)))
        dialog.close()

    def test_old_accident_without_dpn_do_unchanged(self) -> None:
        accident = self._create()
        keys = self._keys(accident)
        self.assertFalse(keys & POST_DPN_OBLIGATION_KEYS)
        original = self._done_original_rows(accident)
        self.assertEqual(self._summary(accident, original), "done")
        self.assertEqual(self._summary(accident, []), "waiting")

        short = self._create(druh_urazu=KIND_UP_TO_3, dpn_do=date(2026, 4, 3), jmeno_prijmeni="Krátká")
        self.assertFalse(self._post_dpn_keys(short))
        self.assertEqual(self._keys(short), {OBLIGATION_OO_OHLASENI})

    def test_existing_reporting_still_works(self) -> None:
        accident = self._create()
        self.assertIn(OBLIGATION_OO_OHLASENI, self._keys(accident))
        self.assertIn(OBLIGATION_ZP_ZASLANI, self._keys(accident))
        self.assertIn(OBLIGATION_EZOP, self._keys(accident))
        self.assertIn(OBLIGATION_ZAMESTNANEC_PREDANI, self._keys(accident))
        self.assertIn(OBLIGATION_OO_PREDANI, self._keys(accident))
        self.assertEqual(
            self._summary(accident, [{"key": OBLIGATION_OO_OHLASENI, "datum": "2026-04-02"}]),
            "waiting",
        )
        self.assertEqual(self._summary(accident, self._done_original_rows(accident)), "done")

        dialog = SetreniDialog(accident=accident)
        self.assertIn(OBLIGATION_OO_OHLASENI, self._admin_keys(dialog))
        self.assertFalse(self._visible_dpn_keys(dialog))
        dialog.close()

    def test_setreni_dialog_shows_concrete_recipients(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        dialog = SetreniDialog(accident=accident)
        visible = self._visible_dpn_keys(dialog)
        self.assertEqual(set(visible), COMMON_POST_DPN)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, self._admin_keys(dialog))

        portal = self._row_by_key(dialog, OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL)
        self.assertEqual(portal.get("fixed_sending_method"), METHOD_PORTAL_SUIP)
        self.assertIsNone(portal.get("lhuta"))
        self.assertEqual(
            [child.text() for child in portal["zpusob"].findChildren(QRadioButton)],
            [METHOD_PORTAL_SUIP],
        )

        employee = self._row_by_key(dialog, OBLIGATION_AKTUALIZACE_ZAMESTNANEC)
        methods = [child.text() for child in employee["zpusob"].findChildren(QRadioButton)]
        self.assertIn("Osobně", methods)
        self.assertIn("E-mail", methods)
        self.assertIsNone(employee.get("lhuta"))
        self.assertIsNone(
            obligation_default_deadline(
                date(2026, 4, 1),
                obligation_key=OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
            )
        )
        dialog.close()

    def test_overview_follows_reporting_rows(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        current = self._saved_data(accident.id)
        original = self._done_original_rows(accident, current)
        saved = self._write_saved(
            accident.id,
            {
                "admin_ohlaseni": [row for row in original if row["key"] == OBLIGATION_OO_OHLASENI],
                "admin_zaslani": [row for row in original if row["key"] != OBLIGATION_OO_OHLASENI]
                + [
                    {
                        "key": OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                        "datum": "2026-04-16",
                        "zpusob": METHOD_PORTAL_SUIP,
                    }
                ],
            },
        )
        overview = dpn_record_update_overview_from_saved_data(accident, saved)
        self.assertTrue(overview["portal_suip_done"])
        self.assertEqual(overview["portal_suip_date"], "2026-04-16")
        self.assertFalse(overview["signed_record_done"])

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertEqual(tab.overview_hint.text(), OVERVIEW_SOURCE_HINT)
        self.assertTrue(tab.portal_suip_done.isChecked())
        self.assertFalse(tab.signed_record_done.isChecked())
        self.assertFalse(tab.portal_suip_done.isEnabled())
        dialog.close()

        remaining = [
            {"key": key, "datum": "2026-04-17"}
            for key in (
                OBLIGATION_AKTUALIZACE_ZP,
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                OBLIGATION_AKTUALIZACE_OO,
            )
        ]
        saved = self._write_saved(
            accident.id,
            {
                "admin_zaslani": [
                    row
                    for row in saved.get("admin_zaslani") or []
                    if row.get("key") != OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL
                ]
                + [
                    {
                        "key": OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                        "datum": "2026-04-16",
                        "zpusob": METHOD_PORTAL_SUIP,
                    }
                ]
                + remaining,
            },
        )
        all_rows = obligation_rows_for_summary(accident, saved)
        self.assertEqual(self._summary(accident, all_rows, saved), "done")
        overview = dpn_record_update_overview_from_saved_data(accident, saved)
        self.assertTrue(overview["signed_record_done"])
        self.assertEqual(overview["signed_record_date"], "2026-04-17")

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertTrue(tab.signed_record_done.isChecked())
        dialog.close()

    def test_clearing_dpn_do_keeps_completed_history(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        saved = self._write_saved(
            accident.id,
            {
                "admin_zaslani": [
                    {
                        "key": OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                        "datum": "2026-04-16",
                        "zpusob": METHOD_PORTAL_SUIP,
                        "upresneni": "podání 123",
                    }
                ]
            },
        )
        self.assertTrue(
            row_is_done(
                next(
                    row
                    for row in saved["admin_zaslani"]
                    if row["key"] == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL
                )
            )
        )

        cleared = accident_service.update_accident(accident.id, dpn_do=None)
        self.assertFalse(self._post_dpn_keys(cleared))
        kept = self._saved_data(cleared.id)
        portal = next(
            row
            for row in kept.get("admin_zaslani") or []
            if row.get("key") == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL
        )
        self.assertEqual(portal.get("datum"), "2026-04-16")
        self.assertEqual(portal.get("upresneni"), "podání 123")

        dialog = SetreniDialog(accident=cleared)
        self.assertIn(OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL, self._visible_dpn_keys(dialog))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
