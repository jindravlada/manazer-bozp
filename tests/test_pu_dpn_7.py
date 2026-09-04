"""PU-DPN-7 – automatické vyhodnocení mimořádné pracovnělékařské prohlídky."""

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

from PySide6.QtWidgets import QApplication, QGroupBox
from sqlalchemy import inspect as sa_inspect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-7-"))

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
        CARE_CATEGORY_1_NO_RISK,
        CARE_DPN_OVER_8_WEEKS,
        CARE_EXAM_DATE,
        CARE_EXAM_DEADLINE,
        CARE_EXAM_REASON,
        CARE_EXAM_REQUIRED,
        CARE_EXAM_RESULT,
        CARE_FITNESS_CHANGE_PRESUMED,
        CARE_RETURN_DATE,
        CARE_RETURN_MODE,
        CARE_SEVERE_CONSEQUENCES,
        CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM,
        DPN_CARE_RETURN_KEY,
        DPN_EXTRAORDINARY_EXAM_AFTER_DAYS,
        EXAM_REQUIRED_BANNER_NO,
        EXAM_REQUIRED_BANNER_YES,
        EXAM_REQUIRED_NO,
        EXAM_REQUIRED_YES,
        EXAM_RESULT_FIT,
        RETURN_MODE_SAME,
        apply_dpn_care_return_to_saved_data,
        dpn_care_return_from_saved_data,
        dpn_longer_than_8_weeks,
        evaluate_dpn_care_return,
        exam_deadline_from_return_date,
        extraordinary_exam_required,
        normalize_dpn_care_return,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        add_workdays,
        dpn_calendar_days,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import (
        EXAM_DEADLINE_NEED_RETURN,
        EXAM_DEADLINE_UNTIL_LABEL,
        SECTION_EXAM_EVALUATION,
    )
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
DPN_EQ_8_WEEKS_FROM = date(2026, 1, 1)
DPN_EQ_8_WEEKS_TO = date(2026, 2, 25)
DPN_OVER_8_WEEKS_TO = date(2026, 2, 26)
RETURN_MONDAY = date(2026, 4, 20)


def _pu_dpn_4_payload(**overrides) -> dict:
    data = {
        "exam_required": "ANO",
        "exam_reason": "delší trvání DPN",
        "exam_date": "2026-04-22",
        "exam_result": EXAM_RESULT_FIT,
        "return_date": "2026-04-25",
        "return_mode": RETURN_MODE_SAME,
    }
    data.update(overrides)
    return data


class PuDpn7TestCase(unittest.TestCase):
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
            "accident_date": date(2026, 1, 1),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád z žebříku",
            "dpn_od": date(2026, 4, 1),
            "dpn_do": date(2026, 4, 20),
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

    def test_eight_weeks_boundary_from_dpn_dates(self) -> None:
        self.assertEqual(
            dpn_calendar_days(DPN_EQ_8_WEEKS_FROM, DPN_EQ_8_WEEKS_TO),
            DPN_EXTRAORDINARY_EXAM_AFTER_DAYS,
        )
        self.assertFalse(
            dpn_longer_than_8_weeks(DPN_EQ_8_WEEKS_FROM, DPN_EQ_8_WEEKS_TO)
        )
        self.assertTrue(
            dpn_longer_than_8_weeks(DPN_EQ_8_WEEKS_FROM, DPN_OVER_8_WEEKS_TO)
        )
        evaluated_eq = evaluate_dpn_care_return(
            {}, dpn_od=DPN_EQ_8_WEEKS_FROM, dpn_do=DPN_EQ_8_WEEKS_TO
        )
        evaluated_over = evaluate_dpn_care_return(
            {}, dpn_od=DPN_EQ_8_WEEKS_FROM, dpn_do=DPN_OVER_8_WEEKS_TO
        )
        self.assertEqual(evaluated_eq[CARE_DPN_OVER_8_WEEKS], EXAM_REQUIRED_NO)
        self.assertEqual(evaluated_eq[CARE_EXAM_REQUIRED], EXAM_REQUIRED_NO)
        self.assertEqual(evaluated_over[CARE_DPN_OVER_8_WEEKS], EXAM_REQUIRED_YES)
        self.assertEqual(evaluated_over[CARE_EXAM_REQUIRED], EXAM_REQUIRED_YES)

    def test_category_1_without_risk_is_exception(self) -> None:
        over = {
            CARE_CATEGORY_1_NO_RISK: EXAM_REQUIRED_YES,
        }
        self.assertFalse(
            extraordinary_exam_required(
                over, dpn_od=DPN_EQ_8_WEEKS_FROM, dpn_do=DPN_OVER_8_WEEKS_TO
            )
        )
        self.assertTrue(
            extraordinary_exam_required(
                {CARE_CATEGORY_1_NO_RISK: EXAM_REQUIRED_NO},
                dpn_od=DPN_EQ_8_WEEKS_FROM,
                dpn_do=DPN_OVER_8_WEEKS_TO,
            )
        )
        self.assertTrue(
            extraordinary_exam_required(
                {},
                dpn_od=DPN_EQ_8_WEEKS_FROM,
                dpn_do=DPN_OVER_8_WEEKS_TO,
            )
        )
        still_required = {
            CARE_CATEGORY_1_NO_RISK: EXAM_REQUIRED_YES,
            CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
        }
        self.assertTrue(
            extraordinary_exam_required(
                still_required,
                dpn_od=DPN_EQ_8_WEEKS_FROM,
                dpn_do=DPN_OVER_8_WEEKS_TO,
            )
        )

    def test_manual_checklist_reasons_each_require_exam(self) -> None:
        short = dict(dpn_od=date(2026, 4, 1), dpn_do=date(2026, 4, 20))
        self.assertFalse(extraordinary_exam_required({}, **short))
        self.assertTrue(
            extraordinary_exam_required(
                {CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES}, **short
            )
        )
        self.assertTrue(
            extraordinary_exam_required(
                {CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM: EXAM_REQUIRED_YES},
                **short,
            )
        )
        self.assertTrue(
            extraordinary_exam_required(
                {CARE_FITNESS_CHANGE_PRESUMED: EXAM_REQUIRED_YES}, **short
            )
        )
        self.assertFalse(
            extraordinary_exam_required(
                {
                    CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_NO,
                    CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM: EXAM_REQUIRED_NO,
                    CARE_FITNESS_CHANGE_PRESUMED: EXAM_REQUIRED_NO,
                },
                **short,
            )
        )

    def test_exam_deadline_is_five_workdays_from_return(self) -> None:
        self.assertIsNone(exam_deadline_from_return_date(None))
        self.assertEqual(
            exam_deadline_from_return_date(RETURN_MONDAY),
            add_workdays(RETURN_MONDAY, 5).isoformat(),
        )
        self.assertEqual(exam_deadline_from_return_date(RETURN_MONDAY), "2026-04-27")
        evaluated = evaluate_dpn_care_return(
            {
                CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
                CARE_RETURN_DATE: RETURN_MONDAY,
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
            dpn_od=date(2026, 4, 1),
            dpn_do=date(2026, 4, 20),
        )
        self.assertEqual(evaluated[CARE_EXAM_DEADLINE], "2026-04-27")
        without_return = evaluate_dpn_care_return(
            {CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES},
            dpn_od=date(2026, 4, 1),
            dpn_do=date(2026, 4, 20),
        )
        self.assertIsNone(without_return[CARE_EXAM_DEADLINE])
        not_required = evaluate_dpn_care_return(
            {
                CARE_RETURN_DATE: RETURN_MONDAY,
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
            dpn_od=date(2026, 4, 1),
            dpn_do=date(2026, 4, 20),
        )
        self.assertEqual(not_required[CARE_EXAM_REQUIRED], EXAM_REQUIRED_NO)
        self.assertIsNone(not_required[CARE_EXAM_DEADLINE])

    def test_apply_does_not_copy_dpn_do_into_return_date(self) -> None:
        accident = SimpleNamespace(
            dpn_od=date(2026, 4, 1),
            dpn_do=date(2026, 4, 20),
        )
        updated = apply_dpn_care_return_to_saved_data(
            {},
            accident=accident,
            ui_state={
                CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
        )
        care = dpn_care_return_from_saved_data(updated)
        self.assertIsNone(care[CARE_RETURN_DATE])
        self.assertNotEqual(care[CARE_RETURN_DATE], accident.dpn_do.isoformat())
        self.assertIsNone(care[CARE_EXAM_DEADLINE])

    def test_ui_evaluates_dpn_length_and_banner(self) -> None:
        accident = self._create(
            dpn_od=DPN_EQ_8_WEEKS_FROM,
            dpn_do=DPN_EQ_8_WEEKS_TO,
        )
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        titles = [group.title() for group in tab.findChildren(QGroupBox)]
        self.assertIn(SECTION_EXAM_EVALUATION, titles)
        self.assertFalse(hasattr(tab, "exam_required_ano"))
        self.assertEqual(tab.dpn_over_8_weeks_value.text(), EXAM_REQUIRED_NO)
        self.assertFalse(tab._exam_form.isRowVisible(tab.category_1_row))
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_NO)
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(DPN_OVER_8_WEEKS_TO)
        self.assertEqual(tab.dpn_over_8_weeks_value.text(), EXAM_REQUIRED_YES)
        self.assertTrue(tab._exam_form.isRowVisible(tab.category_1_row))
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_YES)
        tab.category_1_no_risk_ano.setChecked(True)
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_NO)
        tab.severe_consequences_ano.setChecked(True)
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_YES)
        dialog.close()

    def test_ui_checklist_and_deadline(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertEqual(tab.get_dpn_care_return()[CARE_DPN_OVER_8_WEEKS], EXAM_REQUIRED_NO)
        self.assertTrue(tab._exam_followup_widget.isHidden())
        tab.unconsciousness_ano.setChecked(True)
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_YES)
        self.assertFalse(tab._exam_followup_widget.isHidden())
        self.assertEqual(tab.exam_deadline_label.text(), EXAM_DEADLINE_NEED_RETURN)
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertIn("27.04.2026", tab.exam_deadline_label.text())
        self.assertIn(EXAM_DEADLINE_UNTIL_LABEL, tab.exam_deadline_label.text())
        self.assertEqual(
            tab.get_dpn_care_return()[CARE_EXAM_DEADLINE], "2026-04-27"
        )
        tab.fitness_change_ne.setChecked(True)
        tab.unconsciousness_ne.setChecked(True)
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_NO)
        self.assertTrue(tab._exam_followup_widget.isHidden())
        dialog.close()

    def test_return_date_independent_of_dpn_do(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertEqual(dialog.tab_zamestnanec_widget.dpn_do.get_date(), date(2026, 4, 20))
        self.assertIsNone(tab.return_date.get_date())
        tab.severe_consequences_ano.setChecked(True)
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(date(2026, 4, 28))
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        reloaded = accident_service.get_by_id(accident.id)
        self.assertEqual(reloaded.dpn_do, date(2026, 4, 20))
        care = dpn_care_return_from_saved_data(self._saved_data(reloaded.id))
        self.assertEqual(care[CARE_RETURN_DATE], "2026-04-28")
        self.assertNotEqual(care[CARE_RETURN_DATE], reloaded.dpn_do.isoformat())
        self.assertEqual(care[CARE_EXAM_DEADLINE], "2026-05-06")

    def test_save_reload_computed_result(self) -> None:
        accident = self._create(
            dpn_od=DPN_EQ_8_WEEKS_FROM,
            dpn_do=DPN_OVER_8_WEEKS_TO,
        )
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.category_1_no_risk_ne.setChecked(True)
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        tab.exam_date.set_date_value(date(2026, 4, 22))
        tab.exam_result.setCurrentIndex(tab.exam_result.findData(EXAM_RESULT_FIT))
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(saved[CARE_DPN_OVER_8_WEEKS], EXAM_REQUIRED_YES)
        self.assertEqual(saved[CARE_CATEGORY_1_NO_RISK], EXAM_REQUIRED_NO)
        self.assertEqual(saved[CARE_EXAM_REQUIRED], EXAM_REQUIRED_YES)
        self.assertEqual(saved[CARE_EXAM_DEADLINE], "2026-04-27")
        self.assertEqual(saved[CARE_RETURN_DATE], "2026-04-20")

        reopened = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = reopened.tab_po_ukonceni_dpn_widget
        self.assertEqual(tab.get_dpn_care_return(), saved)
        self.assertEqual(tab.exam_required_banner.text(), EXAM_REQUIRED_BANNER_YES)
        self.assertTrue(tab.category_1_no_risk_ne.isChecked())
        self.assertIn("27.04.2026", tab.exam_deadline_label.text())
        reopened.close()

    def test_pu_dpn_4_json_still_loads_and_roundtrips(self) -> None:
        accident = self._create()
        saved = self._saved_data(accident.id)
        saved[DPN_CARE_RETURN_KEY] = _pu_dpn_4_payload()
        self._write_saved_data(accident.id, saved)

        loaded = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(loaded[CARE_EXAM_REQUIRED], EXAM_REQUIRED_YES)
        self.assertEqual(loaded[CARE_EXAM_REASON], "delší trvání DPN")
        self.assertEqual(loaded[CARE_EXAM_DATE], "2026-04-22")
        self.assertEqual(loaded[CARE_EXAM_RESULT], EXAM_RESULT_FIT)
        self.assertEqual(loaded[CARE_RETURN_DATE], "2026-04-25")
        self.assertEqual(loaded[CARE_RETURN_MODE], RETURN_MODE_SAME)
        self.assertEqual(loaded[CARE_CATEGORY_1_NO_RISK], "")
        self.assertEqual(normalize_dpn_care_return(_pu_dpn_4_payload())[CARE_EXAM_REASON], "delší trvání DPN")

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertEqual(tab.return_date.get_date(), date(2026, 4, 25))
        self.assertEqual(tab.exam_date.get_date(), date(2026, 4, 22))
        self.assertEqual(tab.exam_result.currentData(), EXAM_RESULT_FIT)
        self.assertEqual(tab.return_mode.currentData(), RETURN_MODE_SAME)
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        after = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(after[CARE_EXAM_REASON], "delší trvání DPN")
        self.assertEqual(after[CARE_EXAM_DATE], "2026-04-22")
        self.assertEqual(after[CARE_EXAM_RESULT], EXAM_RESULT_FIT)
        self.assertEqual(after[CARE_RETURN_DATE], "2026-04-25")
        self.assertEqual(after[CARE_RETURN_MODE], RETURN_MODE_SAME)
        self.assertNotIn("diagnóza", json.dumps(after, ensure_ascii=False))

    def test_care_save_does_not_add_db_columns(self) -> None:
        accident = self._create()
        before = self._snapshot(accident)
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.severe_consequences_ano.setChecked(True)
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()
        after = self._snapshot(accident_service.get_by_id(accident.id))
        self.assertEqual(set(after), set(before))
        self.assertIn(DPN_CARE_RETURN_KEY, self._saved_data(accident.id))


if __name__ == "__main__":
    unittest.main()
