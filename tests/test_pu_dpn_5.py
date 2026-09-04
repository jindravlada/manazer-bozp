"""PU-DPN-5 – míra odpovědnosti zaměstnavatele po ukončení DPN."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import inspect as sa_inspect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-5-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_dpn_care import (
        DPN_CARE_RETURN_KEY,
        dpn_care_return_from_saved_data,
    )
    from moduly.kniha_urazu.sluzby.accident_dpn_responsibility import (
        DPN_EMPLOYER_RESPONSIBILITY_KEY,
        PERCENT_MAX,
        PERCENT_MIN,
        RESP_NOTE,
        RESP_PROPOSED_PERCENT,
        RESP_RECOGNIZED_PERCENT,
        apply_dpn_employer_responsibility_to_saved_data,
        dpn_employer_responsibility_from_saved_data,
        normalize_dpn_employer_responsibility,
        normalize_percent,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_OO_OHLASENI,
        applicable_obligations,
        is_obligation_relevant,
        obligations_summary_state,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
TODAY = date(2026, 4, 20)
COMPENSATION_KEYS = (
    "bolestne",
    "ztrata_na_vydelku",
    "zsu",
    "naklady_leceni",
    "odskodneni",
)


class PuDpn5TestCase(unittest.TestCase):
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
            "popis_urazoveho_deje": "Pád z žebříku",
            "dpn_od": date(2026, 4, 1),
            "dpn_do": None,
            "opatreni": "Kontrola žebříků",
            "zranena_cast_tela": "Levé zápěstí",
        }
        data.update(overrides)
        return accident_service.create_accident(**data)

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not str(raw).strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _write_saved_data(self, accident_id: int, data: dict) -> None:
        investigation_service.save_zajisteni_dukazu(
            accident_id,
            json.dumps(data, ensure_ascii=False),
        )

    def _snapshot(self, accident: Accident) -> dict:
        mapper = sa_inspect(Accident)
        return {
            attr.key: getattr(accident, attr.key)
            for attr in mapper.column_attrs
            if attr.key != "updated_at"
        }

    def test_percent_range_accepts_0_to_100_and_rejects_outside(self) -> None:
        self.assertEqual(normalize_percent(0), PERCENT_MIN)
        self.assertEqual(normalize_percent(100), PERCENT_MAX)
        self.assertEqual(normalize_percent("50 %"), 50)
        self.assertIsNone(normalize_percent(None))
        self.assertIsNone(normalize_percent(""))
        self.assertIsNone(normalize_percent(-1))
        self.assertIsNone(normalize_percent(101))
        self.assertIsNone(normalize_percent("abc"))

        data = normalize_dpn_employer_responsibility(
            {
                RESP_PROPOSED_PERCENT: 0,
                RESP_RECOGNIZED_PERCENT: 101,
                RESP_NOTE: "  bez částek  ",
            }
        )
        self.assertEqual(data[RESP_PROPOSED_PERCENT], 0)
        self.assertIsNone(data[RESP_RECOGNIZED_PERCENT])
        self.assertEqual(data[RESP_NOTE], "bez částek")

    def test_empty_values_are_allowed_and_not_copied(self) -> None:
        accident = SimpleNamespace(dpn_do=date(2026, 4, 20))
        updated = apply_dpn_employer_responsibility_to_saved_data(
            {},
            accident=accident,
            ui_state={RESP_PROPOSED_PERCENT: 40},
        )
        data = dpn_employer_responsibility_from_saved_data(updated)
        self.assertEqual(data[RESP_PROPOSED_PERCENT], 40)
        self.assertIsNone(data[RESP_RECOGNIZED_PERCENT])
        self.assertEqual(data[RESP_NOTE], "")

        empty = apply_dpn_employer_responsibility_to_saved_data(
            {},
            accident=accident,
            ui_state={},
        )
        self.assertNotIn(DPN_EMPLOYER_RESPONSIBILITY_KEY, empty)

    def test_section_inactive_without_dpn_do(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertFalse(tab.is_content_active())
        self.assertFalse(tab.proposed_percent.isEnabled())
        self.assertFalse(tab.recognized_percent.isEnabled())
        self.assertFalse(tab.responsibility_note.isEnabled())
        dialog.close()

    def test_section_active_after_dpn_end_starts_empty(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertTrue(tab.is_content_active())
        self.assertTrue(tab.proposed_percent.isEnabled())
        self.assertTrue(tab.recognized_percent.isEnabled())
        self.assertEqual(tab.proposed_percent.minimum(), -1)
        self.assertEqual(tab.proposed_percent.maximum(), 100)
        self.assertEqual(tab.recognized_percent.maximum(), 100)
        state = tab.get_dpn_employer_responsibility()
        self.assertIsNone(state[RESP_PROPOSED_PERCENT])
        self.assertIsNone(state[RESP_RECOGNIZED_PERCENT])
        self.assertEqual(state[RESP_NOTE], "")
        dialog.close()

    def test_save_and_reload_independent_values(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.proposed_percent.setValue(60)
        tab.recognized_percent.setValue(40)
        tab.responsibility_note.setPlainText("Uzavřeno dohodou, bez částek.")
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = dpn_employer_responsibility_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(saved[RESP_PROPOSED_PERCENT], 60)
        self.assertEqual(saved[RESP_RECOGNIZED_PERCENT], 40)
        self.assertEqual(saved[RESP_NOTE], "Uzavřeno dohodou, bez částek.")
        for key in COMPENSATION_KEYS:
            self.assertNotIn(key, saved)

        reopened = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = reopened.tab_po_ukonceni_dpn_widget
        reloaded = tab.get_dpn_employer_responsibility()
        self.assertEqual(reloaded, saved)
        self.assertEqual(tab.proposed_percent.value(), 60)
        self.assertEqual(tab.recognized_percent.value(), 40)
        self.assertEqual(tab.responsibility_note.toPlainText(), "Uzavřeno dohodou, bez částek.")
        reopened.close()

    def test_zero_percent_is_kept_and_differs_from_empty(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.proposed_percent.setValue(0)
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = dpn_employer_responsibility_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(saved[RESP_PROPOSED_PERCENT], 0)
        self.assertIsNone(saved[RESP_RECOGNIZED_PERCENT])

        reopened = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        self.assertEqual(reopened.tab_po_ukonceni_dpn_widget.proposed_percent.value(), 0)
        self.assertIsNone(
            reopened.tab_po_ukonceni_dpn_widget.get_dpn_employer_responsibility()[
                RESP_RECOGNIZED_PERCENT
            ]
        )
        reopened.close()

    def test_old_accident_unchanged_without_responsibility_data(self) -> None:
        accident = self._create(osobni_cislo="123", misto_urazu="Sklad")
        saved = self._saved_data(accident.id)
        saved["admin_zaslani"] = [
            {"key": OBLIGATION_OO_OHLASENI, "datum": "2026-04-05"},
        ]
        saved[DPN_CARE_RETURN_KEY] = {
            "exam_required": "NE",
            "exam_reason": "",
            "exam_date": None,
            "exam_result": "",
            "return_date": None,
            "return_mode": "dosud nenastoupil",
        }
        self._write_saved_data(accident.id, saved)
        before_accident = self._snapshot(accident_service.get_by_id(accident.id))
        before_json = self._saved_data(accident.id)

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        self.assertFalse(dialog.tab_po_ukonceni_dpn_widget.is_content_active())
        after_open = self._snapshot(accident_service.get_by_id(accident.id))
        self.assertEqual(after_open, before_accident)
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        after_json = self._saved_data(accident.id)
        reloaded = accident_service.get_by_id(accident.id)
        self.assertIsNone(reloaded.dpn_do)
        self.assertEqual(reloaded.osobni_cislo, "123")
        self.assertNotIn(DPN_EMPLOYER_RESPONSIBILITY_KEY, after_json)
        self.assertEqual(after_json.get("admin_zaslani"), before_json.get("admin_zaslani"))
        self.assertEqual(
            dpn_care_return_from_saved_data(after_json),
            dpn_care_return_from_saved_data(before_json),
        )
        self.assertFalse(
            is_obligation_relevant(
                reloaded,
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
            )
        )

    def test_responsibility_save_does_not_change_care_or_zou(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        saved = self._saved_data(accident.id)
        saved["admin_zaslani"] = [
            {"key": OBLIGATION_OO_OHLASENI, "datum": "2026-04-05"},
        ]
        saved[DPN_CARE_RETURN_KEY] = {
            "exam_required": "NE",
            "exam_reason": "",
            "exam_date": None,
            "exam_result": "",
            "return_date": "2026-04-25",
            "return_mode": "návrat na dosavadní práci",
        }
        self._write_saved_data(accident.id, saved)
        before = self._saved_data(accident.id)
        before_keys = {item.key for item in applicable_obligations(accident, saved_data=before)}
        before_zou = obligations_summary_state(
            accident,
            before.get("admin_zaslani") or [],
            TODAY,
            saved_data=before,
            union_organization_active=True,
        )

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        self.assertNotIn("dpn_record_update", dialog.get_data())
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.proposed_percent.setValue(70)
        tab.recognized_percent.setValue(100)
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        after = self._saved_data(accident.id)
        after_accident = accident_service.get_by_id(accident.id)
        after_keys = {
            item.key for item in applicable_obligations(after_accident, saved_data=after)
        }
        after_zou = obligations_summary_state(
            after_accident,
            after.get("admin_zaslani") or [],
            TODAY,
            saved_data=after,
            union_organization_active=True,
        )
        self.assertEqual(after.get("admin_zaslani"), before.get("admin_zaslani"))
        self.assertEqual(
            dpn_care_return_from_saved_data(after),
            dpn_care_return_from_saved_data(before),
        )
        self.assertEqual(after_keys, before_keys)
        self.assertEqual(after_zou, before_zou)
        self.assertEqual(
            dpn_employer_responsibility_from_saved_data(after)[RESP_PROPOSED_PERCENT],
            70,
        )
        self.assertEqual(
            dpn_employer_responsibility_from_saved_data(after)[RESP_RECOGNIZED_PERCENT],
            100,
        )


if __name__ == "__main__":
    unittest.main()
