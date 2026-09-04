"""PU-DPN-7c – pořadí návratu a mimořádné prohlídky podle pracovního postupu."""

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

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-7c-"))

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
        CARE_EXAM_DEADLINE,
        CARE_EXAM_REQUIRED,
        CARE_EXAM_RESULT,
        CARE_RETURN_DATE,
        CARE_RETURN_MODE,
        CARE_SEVERE_CONSEQUENCES,
        DPN_CARE_RETURN_KEY,
        EXAM_REQUIRED_YES,
        EXAM_RESULT_FIT,
        RETURN_MODE_SAME,
        dpn_care_return_from_saved_data,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
RETURN_MONDAY = date(2026, 4, 20)

REQUIRED_SEQUENCE = (
    "return_date",
    "exam_deadline",
    "exam_date",
    "exam_result",
    "return_mode",
)
NOT_REQUIRED_SEQUENCE = ("return_date", "return_mode")


class PuDpn7cTestCase(unittest.TestCase):
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

    def test_order_when_exam_required(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.severe_consequences_ano.setChecked(True)
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertEqual(tab.visible_care_sequence(), REQUIRED_SEQUENCE)
        care_layout = tab.section_groups[1].layout()
        self.assertIs(care_layout.itemAt(1).widget(), tab._return_date_widget)
        self.assertIs(care_layout.itemAt(2).widget(), tab._exam_followup_widget)
        self.assertIs(care_layout.itemAt(3).widget(), tab._return_mode_widget)
        self.assertFalse(tab._exam_followup_widget.isHidden())
        dialog.close()

    def test_order_when_exam_not_required(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertEqual(tab.visible_care_sequence(), NOT_REQUIRED_SEQUENCE)
        self.assertTrue(tab._exam_followup_widget.isHidden())
        care_layout = tab.section_groups[1].layout()
        self.assertIs(care_layout.itemAt(1).widget(), tab._return_date_widget)
        self.assertIs(care_layout.itemAt(3).widget(), tab._return_mode_widget)
        dialog.close()

    def test_saved_care_data_unchanged_after_reorder(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.severe_consequences_ano.setChecked(True)
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        tab.exam_date.set_date_value(date(2026, 4, 22))
        tab.exam_result.setCurrentIndex(tab.exam_result.findData(EXAM_RESULT_FIT))
        before = tab.get_dpn_care_return()
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(saved, before)
        self.assertEqual(saved[CARE_EXAM_REQUIRED], EXAM_REQUIRED_YES)
        self.assertEqual(saved[CARE_SEVERE_CONSEQUENCES], EXAM_REQUIRED_YES)
        self.assertEqual(saved[CARE_RETURN_DATE], "2026-04-20")
        self.assertEqual(saved[CARE_RETURN_MODE], RETURN_MODE_SAME)
        self.assertEqual(saved[CARE_EXAM_DATE], "2026-04-22")
        self.assertEqual(saved[CARE_EXAM_RESULT], EXAM_RESULT_FIT)
        self.assertEqual(saved[CARE_EXAM_DEADLINE], "2026-04-27")

        reopened = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        self.assertEqual(
            reopened.tab_po_ukonceni_dpn_widget.get_dpn_care_return(), saved
        )
        accident_service.update_accident(accident.id, **reopened.get_data())
        reopened.close()

        after = dpn_care_return_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(after, saved)
        self.assertIn(DPN_CARE_RETURN_KEY, self._saved_data(accident.id))


if __name__ == "__main__":
    unittest.main()
