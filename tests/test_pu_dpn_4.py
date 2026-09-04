"""PU-DPN-4 – péče a návrat do práce po ukončení DPN."""

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

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-4-"))

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
        CARE_EXAM_DATE,
        CARE_EXAM_REASON,
        CARE_EXAM_REQUIRED,
        CARE_EXAM_RESULT,
        CARE_RETURN_DATE,
        CARE_RETURN_MODE,
        CARE_SEVERE_CONSEQUENCES,
        DPN_CARE_RETURN_KEY,
        EXAM_REQUIRED_NO,
        EXAM_REQUIRED_YES,
        EXAM_RESULT_FIT,
        RETURN_MODE_NOT_STARTED,
        RETURN_MODE_SAME,
        apply_dpn_care_return_to_saved_data,
        dpn_care_return_from_saved_data,
        exam_details_relevant,
        normalize_dpn_care_return,
        return_date_relevant,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_OO_OHLASENI,
        POST_DPN_OBLIGATION_KEYS,
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


class PuDpn4TestCase(unittest.TestCase):
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

    def _fill_care(self, tab, *, exam_required=EXAM_REQUIRED_YES) -> None:
        if exam_required == EXAM_REQUIRED_YES:
            tab.severe_consequences_ano.setChecked(True)
            tab.exam_date.set_date_value(date(2026, 4, 22))
            tab.exam_result.setCurrentIndex(tab.exam_result.findData(EXAM_RESULT_FIT))
        tab.return_date.set_date_value(date(2026, 4, 25))
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))

    def test_normalize_drops_unknown_and_keeps_labels(self) -> None:
        data = normalize_dpn_care_return(
            {
                CARE_EXAM_REQUIRED: "Ano",
                CARE_EXAM_REASON: "  delší DPN  ",
                CARE_EXAM_DATE: date(2026, 4, 22),
                CARE_EXAM_RESULT: "diagnóza zlomenina",
                CARE_RETURN_DATE: "2026-04-25",
                CARE_RETURN_MODE: "návrat na dosavadní práci",
            }
        )
        self.assertEqual(data[CARE_EXAM_REQUIRED], EXAM_REQUIRED_YES)
        self.assertEqual(data[CARE_EXAM_REASON], "delší DPN")
        self.assertEqual(data[CARE_EXAM_DATE], "2026-04-22")
        self.assertEqual(data[CARE_EXAM_RESULT], "")
        self.assertEqual(data[CARE_RETURN_DATE], "2026-04-25")
        self.assertEqual(data[CARE_RETURN_MODE], RETURN_MODE_SAME)
        self.assertFalse(exam_details_relevant(data))
        self.assertTrue(
            exam_details_relevant({CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES})
        )
        self.assertTrue(return_date_relevant(data))
        self.assertFalse(
            return_date_relevant({CARE_RETURN_MODE: RETURN_MODE_NOT_STARTED})
        )

    def test_apply_does_not_copy_dpn_do_into_return_date(self) -> None:
        accident = SimpleNamespace(dpn_do=date(2026, 4, 20))
        updated = apply_dpn_care_return_to_saved_data(
            {},
            accident=accident,
            ui_state={CARE_RETURN_MODE: RETURN_MODE_SAME},
        )
        care = dpn_care_return_from_saved_data(updated)
        self.assertEqual(care[CARE_EXAM_REQUIRED], EXAM_REQUIRED_NO)
        self.assertIsNone(care[CARE_RETURN_DATE])
        self.assertNotEqual(care[CARE_RETURN_DATE], accident.dpn_do.isoformat())

    def test_section_inactive_without_dpn_do(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertFalse(tab.is_content_active())
        self.assertFalse(tab.sections_widget.isEnabled())
        self.assertTrue(tab.sections_widget.isHidden())
        self.assertFalse(tab.severe_consequences_ano.isEnabled())
        self.assertFalse(tab.return_mode.isEnabled())
        dialog.close()

    def test_section_active_after_dpn_end(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 4, 20))
        self.assertTrue(tab.is_content_active())
        self.assertTrue(tab.sections_widget.isEnabled())
        self.assertTrue(tab.severe_consequences_ano.isEnabled())
        self.assertTrue(tab.severe_consequences_ne.isEnabled())
        self.assertTrue(tab.return_mode.isEnabled())
        self.assertIsNone(tab.return_date.get_date())
        self.assertIsNone(tab.get_dpn_care_return()[CARE_RETURN_DATE])
        dialog.close()

    def test_exam_fields_relevant_only_when_required(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget

        self.assertTrue(tab._exam_followup_widget.isHidden())
        self.assertFalse(tab.exam_date.isEnabled())
        self.assertFalse(tab.exam_result.isEnabled())

        tab.severe_consequences_ano.setChecked(True)
        self.assertFalse(tab._exam_followup_widget.isHidden())
        self.assertTrue(tab.exam_date.isEnabled())
        self.assertTrue(tab.exam_result.isEnabled())
        dialog.close()

    def test_return_date_hidden_when_not_started(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertTrue(tab._return_form.isRowVisible(tab.return_date))
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_NOT_STARTED))
        self.assertFalse(tab._return_form.isRowVisible(tab.return_date))
        self.assertFalse(tab.return_date.isEnabled())
        dialog.close()

    def test_save_and_reload_care_return(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        self._fill_care(dialog.tab_po_ukonceni_dpn_widget)
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(saved[CARE_EXAM_REQUIRED], EXAM_REQUIRED_YES)
        self.assertEqual(saved[CARE_SEVERE_CONSEQUENCES], EXAM_REQUIRED_YES)
        self.assertEqual(saved[CARE_EXAM_DATE], "2026-04-22")
        self.assertEqual(saved[CARE_EXAM_RESULT], EXAM_RESULT_FIT)
        self.assertEqual(saved[CARE_RETURN_DATE], "2026-04-25")
        self.assertEqual(saved[CARE_RETURN_MODE], RETURN_MODE_SAME)

        reopened = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = reopened.tab_po_ukonceni_dpn_widget
        reloaded = tab.get_dpn_care_return()
        self.assertEqual(reloaded, saved)
        self.assertTrue(tab.severe_consequences_ano.isChecked())
        self.assertEqual(tab.exam_date.get_date(), date(2026, 4, 22))
        self.assertEqual(tab.exam_result.currentData(), EXAM_RESULT_FIT)
        self.assertEqual(tab.return_date.get_date(), date(2026, 4, 25))
        self.assertEqual(tab.return_mode.currentData(), RETURN_MODE_SAME)
        reopened.close()

    def test_exam_not_required_saves_without_date_or_result(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(date(2026, 4, 21))
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(saved[CARE_EXAM_REQUIRED], EXAM_REQUIRED_NO)
        self.assertIsNone(saved[CARE_EXAM_DATE])
        self.assertEqual(saved[CARE_EXAM_RESULT], "")
        self.assertEqual(saved[CARE_RETURN_DATE], "2026-04-21")

    def test_return_date_is_independent_of_dpn_do(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertEqual(dialog.tab_zamestnanec_widget.dpn_do.get_date(), date(2026, 4, 20))
        self.assertIsNone(tab.return_date.get_date())

        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(date(2026, 4, 28))
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        reloaded = accident_service.get_by_id(accident.id)
        self.assertEqual(reloaded.dpn_do, date(2026, 4, 20))
        care = dpn_care_return_from_saved_data(self._saved_data(reloaded.id))
        self.assertEqual(care[CARE_RETURN_DATE], "2026-04-28")
        self.assertNotEqual(care[CARE_RETURN_DATE], reloaded.dpn_do.isoformat())

    def test_old_accident_unchanged_without_care_data(self) -> None:
        accident = self._create(osobni_cislo="123", misto_urazu="Sklad")
        saved = self._saved_data(accident.id)
        saved["admin_zaslani"] = [
            {"key": OBLIGATION_OO_OHLASENI, "datum": "2026-04-05"},
        ]
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
        self.assertEqual(reloaded.jmeno_prijmeni, "Jan Novák")
        self.assertEqual(reloaded.osobni_cislo, "123")
        self.assertEqual(reloaded.misto_urazu, "Sklad")
        self.assertNotIn(DPN_CARE_RETURN_KEY, after_json)
        self.assertEqual(after_json.get("admin_zaslani"), before_json.get("admin_zaslani"))
        self.assertFalse(
            is_obligation_relevant(
                accident_service.get_by_id(accident.id),
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
            )
        )

    def test_care_save_does_not_change_reporting_or_zou(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        saved = self._saved_data(accident.id)
        saved["admin_zaslani"] = [
            {"key": OBLIGATION_OO_OHLASENI, "datum": "2026-04-05"},
        ]
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
        self._fill_care(dialog.tab_po_ukonceni_dpn_widget)
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
        self.assertEqual(after_keys, before_keys)
        self.assertEqual(after_zou, before_zou)
        self.assertTrue(POST_DPN_OBLIGATION_KEYS & after_keys)
        self.assertIn(DPN_CARE_RETURN_KEY, after)
        self.assertNotIn("diagnóza", json.dumps(after[DPN_CARE_RETURN_KEY], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
