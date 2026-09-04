"""PU-DPN-3a – zákonná pojišťovna mimo indikátor ZoÚ."""

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

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-3a-"))

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
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_AKTUALIZACE_OO,
        OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
        OBLIGATION_AKTUALIZACE_ZP,
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU,
        OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
        POST_DPN_OBLIGATION_KEYS,
        ZAKONNA_POJISTOVNA_KEYS,
        applicable_obligations,
        is_obligation_relevant,
        is_obligation_visible,
        is_row_relevant,
        obligation_key_from_row,
        obligation_rows_for_summary,
        obligations_summary_state,
        zakonna_together_checkbox_default,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_table import AccidentTable
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
TODAY = date(2026, 4, 20)
COMMON_POST_DPN = {
    OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
    OBLIGATION_AKTUALIZACE_ZP,
    OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
    OBLIGATION_AKTUALIZACE_OO,
}


class PuDpn3aTestCase(unittest.TestCase):
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

    def _keys(self, accident, saved_data=None) -> set[str]:
        return {
            item.key
            for item in applicable_obligations(
                accident,
                saved_data=saved_data,
                union_organization_active=True,
            )
        }

    def _done_original_and_dpn(self, accident, saved_data=None) -> list[dict]:
        return [
            {"key": item.key, "datum": "2026-04-16"}
            for item in applicable_obligations(
                accident,
                saved_data=saved_data,
                union_organization_active=True,
            )
        ]

    def _done_without_dpn(self, accident, saved_data=None) -> list[dict]:
        return [
            {"key": item.key, "datum": "2026-04-05"}
            for item in applicable_obligations(
                accident,
                saved_data=saved_data,
                union_organization_active=True,
            )
            if item.key not in POST_DPN_OBLIGATION_KEYS
        ]

    def _summary(self, accident, rows, saved_data=None):
        return obligations_summary_state(
            accident,
            rows,
            TODAY,
            saved_data=saved_data,
            union_organization_active=True,
        )

    def _zakonna_row(self, dialog: SetreniDialog, key: str) -> dict:
        for row in getattr(dialog, "admin_zakonna_rows", []):
            if row.get("key") == key:
                return row
        self.fail(f"Položka {key} nebyla nalezena.")

    def test_no_existing_claim_fields_on_accident(self) -> None:
        self.assertFalse(hasattr(Accident, "cislo_pojistne_udalosti"))
        self.assertFalse(hasattr(Accident, "datum_nahlasi_zakonne_pojistovne"))
        self.assertFalse(hasattr(Accident, "zakonna_pojistovna"))

    def test_never_relevant_for_zou(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        for key in ZAKONNA_POJISTOVNA_KEYS:
            self.assertFalse(is_obligation_relevant(accident, key))
        self.assertFalse(self._keys(accident) & ZAKONNA_POJISTOVNA_KEYS)
        self.assertTrue(COMMON_POST_DPN.issubset(self._keys(accident)))

    def test_legacy_kooperativa_maps_to_hlaseni_but_not_zou(self) -> None:
        self.assertEqual(
            obligation_key_from_row({"nazev": "Kooperativa"}),
            OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
        )
        accident = self._create(dpn_do=date(2026, 4, 15))
        self.assertFalse(is_row_relevant(accident, {"nazev": "Kooperativa"}))

    def test_claim_during_dpn_then_update_after(self) -> None:
        accident = self._create()
        saved = self._write_saved(
            accident.id,
            {
                "admin_zaslani": [
                    {
                        "key": OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
                        "datum": "2026-04-08",
                        "upresneni": "PU-11",
                    }
                ]
            },
        )
        dialog = SetreniDialog(accident=accident)
        hlaseni = self._zakonna_row(dialog, OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI)
        self.assertTrue(dialog._admin_row_relevant(hlaseni))
        self.assertFalse(
            dialog._admin_row_relevant(
                self._zakonna_row(dialog, OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU)
            )
        )
        self.assertFalse(dialog.zakonna_together_checkbox.isVisible())
        dialog.close()

        updated = accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 15))
        dialog = SetreniDialog(accident=updated)
        hlaseni = self._zakonna_row(dialog, OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI)
        aktualizace = self._zakonna_row(
            dialog, OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU
        )
        self.assertTrue(dialog._admin_row_relevant(hlaseni))
        self.assertTrue(dialog._admin_row_relevant(aktualizace))
        self.assertEqual(dialog._date_to_json(hlaseni["datum"]), "2026-04-08")
        self.assertEqual(hlaseni["upresneni"].text(), "PU-11")
        self.assertFalse(dialog.zakonna_together_checkbox.isChecked())
        dialog._set_date_widget(aktualizace["datum"], date(2026, 4, 16))
        dialog.accept()

        kept = self._saved_data(updated.id)
        rows = {
            obligation_key_from_row(row): row
            for row in kept.get("admin_zaslani") or []
        }
        self.assertEqual(rows[OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI]["datum"], "2026-04-08")
        self.assertEqual(rows[OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI]["upresneni"], "PU-11")
        self.assertEqual(
            rows[OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU]["datum"], "2026-04-16"
        )

    def test_claim_after_dpn_with_current_zou_is_one_act(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        self.assertTrue(
            zakonna_together_checkbox_default(
                dpn_ended=True,
                hlaseni_row={},
                aktualizace_row={},
            )
        )
        dialog = SetreniDialog(accident=accident)
        self.assertTrue(dialog.zakonna_together_checkbox.isChecked())
        hlaseni = self._zakonna_row(dialog, OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI)
        aktualizace = self._zakonna_row(
            dialog, OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU
        )
        self.assertTrue(dialog._admin_row_relevant(aktualizace))
        dialog._set_date_widget(hlaseni["datum"], date(2026, 4, 16))
        hlaseni["upresneni"].setText("PU-22")
        dialog._sync_zakonna_together()
        self.assertEqual(dialog._date_to_json(aktualizace["datum"]), "2026-04-16")
        dialog.accept()

        kept = self._saved_data(accident.id)
        rows = {
            obligation_key_from_row(row): row
            for row in kept.get("admin_zaslani") or []
        }
        self.assertEqual(rows[OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI]["datum"], "2026-04-16")
        self.assertEqual(
            rows[OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU]["datum"], "2026-04-16"
        )
        self.assertEqual(rows[OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI]["upresneni"], "PU-22")

    def test_zakonna_never_changes_zou_color(self) -> None:
        accident = self._create()
        original = self._done_without_dpn(accident, self._saved_data(accident.id))
        self.assertEqual(self._summary(accident, original, self._saved_data(accident.id)), "done")
        table = AccidentTable()
        self.assertEqual(
            table._zou_color(accident, original, TODAY).name(),
            STATUS_DONE_BG,
        )

        self._write_saved(
            accident.id,
            {
                "admin_zaslani": original
                + [{"key": OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI, "datum": ""}],
            },
        )
        saved = self._saved_data(accident.id)
        self.assertEqual(self._summary(accident, original, saved), "done")

        updated = accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 15))
        original_after = self._done_without_dpn(updated, self._saved_data(updated.id))
        self.assertEqual(self._summary(updated, original_after), "waiting")
        self.assertEqual(
            table._zou_color(updated, original_after, TODAY).name(),
            STATUS_WARNING_BG,
        )

        all_dpn3 = self._done_original_and_dpn(updated, self._saved_data(updated.id))
        mixed = all_dpn3 + [
            {"key": OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI, "datum": ""},
            {"key": OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU, "datum": ""},
        ]
        self.assertEqual(self._summary(updated, mixed, self._saved_data(updated.id)), "done")
        self.assertEqual(
            table._zou_color(updated, mixed, TODAY).name(),
            STATUS_DONE_BG,
        )
        self.assertNotIn(
            OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
            {row["key"] for row in obligation_rows_for_summary(updated, saved)},
        )

    def test_no_duplicates_on_reopen(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        dialog = SetreniDialog(accident=accident)
        first = [row.get("key") for row in dialog.admin_zakonna_rows]
        dialog.accept()
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        second = [row.get("key") for row in dialog.admin_zakonna_rows]
        self.assertEqual(first, second)
        self.assertEqual(first.count(OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI), 1)
        self.assertEqual(first.count(OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU), 1)
        dialog.close()

        saved_rows = self._saved_data(accident.id).get("admin_zaslani") or []
        keys = [
            obligation_key_from_row(row)
            for row in saved_rows
            if obligation_key_from_row(row) in ZAKONNA_POJISTOVNA_KEYS
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_legacy_kooperativa_data_is_kept(self) -> None:
        accident = self._create()
        self._write_saved(
            accident.id,
            {
                "admin_zaslani": [
                    {
                        "nazev": "Kooperativa",
                        "datum": "2026-04-04",
                        "upresneni": "staré hlášení",
                    }
                ]
            },
        )
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        hlaseni = self._zakonna_row(dialog, OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI)
        self.assertEqual(dialog._date_to_json(hlaseni["datum"]), "2026-04-04")
        self.assertEqual(hlaseni["upresneni"].text(), "staré hlášení")
        dialog.close()
        self.assertTrue(
            is_obligation_visible(
                accident,
                OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
            )
        )
        self.assertNotIn(OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI, self._keys(accident))
        self.assertEqual(
            self._summary(accident, [{"key": OBLIGATION_OO_OHLASENI}]),
            "waiting",
        )


if __name__ == "__main__":
    unittest.main()
