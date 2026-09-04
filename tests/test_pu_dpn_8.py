"""PU-DPN-8 – rozsah náhrady pracovního úrazu a dopočtené krácení."""

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

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-8-"))

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
    from moduly.kniha_urazu.sluzby.accident_dpn_responsibility import (
        DPN_EMPLOYER_RESPONSIBILITY_KEY,
        RESP_NOTE,
        RESP_PROPOSED_PERCENT,
        RESP_RECOGNIZED_PERCENT,
        dpn_employer_responsibility_from_saved_data,
        reduction_percent,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import (
        LABEL_COMPENSATION_NOTE,
        LABEL_PROPOSED_COMPENSATION,
        LABEL_RECOGNIZED_COMPENSATION,
        LABEL_REDUCTION,
        PERCENT_SUFFIX,
        SECTION_ROZSAH_NAHRADY,
    )
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


class PuDpn8TestCase(unittest.TestCase):
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

    def _write_saved_data(self, accident_id: int, data: dict) -> None:
        investigation_service.save_zajisteni_dukazu(
            accident_id,
            json.dumps(data, ensure_ascii=False),
        )

    def _open(self):
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        return accident, dialog, dialog.tab_po_ukonceni_dpn_widget

    def test_percent_sign_and_section_labels(self) -> None:
        accident, dialog, tab = self._open()
        titles = [group.title() for group in tab.section_groups]
        self.assertIn(SECTION_ROZSAH_NAHRADY, titles)
        self.assertEqual(tab.proposed_percent.suffix(), PERCENT_SUFFIX)
        self.assertEqual(tab.recognized_percent.suffix(), PERCENT_SUFFIX)
        self.assertIn("%", tab.proposed_percent.suffix())
        self.assertEqual(LABEL_PROPOSED_COMPENSATION, "Navržený rozsah náhrady zaměstnanci:")
        self.assertEqual(
            LABEL_RECOGNIZED_COMPENSATION,
            "Skutečně uznaný rozsah náhrady zaměstnanci:",
        )
        self.assertEqual(LABEL_REDUCTION, "Krácení náhrady:")
        self.assertEqual(LABEL_COMPENSATION_NOTE, "Poznámka k rozsahu náhrady:")
        dialog.close()

    def test_reduction_from_full_partial_and_zero(self) -> None:
        self.assertEqual(reduction_percent(100), 0)
        self.assertEqual(reduction_percent(60), 40)
        self.assertEqual(reduction_percent(0), 100)
        self.assertIsNone(reduction_percent(None))
        self.assertIsNone(reduction_percent(""))

        accident, dialog, tab = self._open()
        tab.proposed_percent.setValue(100)
        tab.recognized_percent.setValue(60)
        self.assertEqual(tab.proposed_reduction_label.text(), "0 %")
        self.assertEqual(tab.recognized_reduction_label.text(), "40 %")
        self.assertTrue(tab.proposed_reduction_label.isVisibleTo(tab))
        self.assertTrue(tab.recognized_reduction_label.isVisibleTo(tab))
        self.assertTrue(tab.proposed_reduction_caption.isVisibleTo(tab))

        tab.proposed_percent.setValue(0)
        self.assertEqual(tab.proposed_reduction_label.text(), "100 %")
        dialog.close()

    def test_empty_hides_reduction(self) -> None:
        accident, dialog, tab = self._open()
        self.assertIsNone(tab.get_dpn_employer_responsibility()[RESP_PROPOSED_PERCENT])
        self.assertFalse(tab.proposed_reduction_label.isVisibleTo(tab))
        self.assertFalse(tab.recognized_reduction_label.isVisibleTo(tab))
        self.assertEqual(tab.proposed_reduction_label.text(), "")
        tab.proposed_percent.setValue(60)
        self.assertTrue(tab.proposed_reduction_label.isVisibleTo(tab))
        self.assertTrue(tab.proposed_reduction_caption.isVisibleTo(tab))
        self.assertEqual(tab.proposed_reduction_label.text(), "40 %")
        tab.proposed_percent.setValue(-1)
        self.assertFalse(tab.proposed_reduction_label.isVisibleTo(tab))
        dialog.close()

    def test_old_data_loads_same_values_with_new_labels(self) -> None:
        accident = self._create()
        saved = self._saved_data(accident.id)
        saved[DPN_EMPLOYER_RESPONSIBILITY_KEY] = {
            "proposed_percent": 70,
            "recognized_percent": 100,
            "note": "Dohoda bez částek",
        }
        self._write_saved_data(accident.id, saved)

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = dialog.tab_po_ukonceni_dpn_widget
        loaded = tab.get_dpn_employer_responsibility()
        self.assertEqual(loaded[RESP_PROPOSED_PERCENT], 70)
        self.assertEqual(loaded[RESP_RECOGNIZED_PERCENT], 100)
        self.assertEqual(loaded[RESP_NOTE], "Dohoda bez částek")
        self.assertEqual(tab.proposed_percent.value(), 70)
        self.assertEqual(tab.recognized_percent.value(), 100)
        self.assertEqual(tab.proposed_reduction_label.text(), "30 %")
        self.assertEqual(tab.recognized_reduction_label.text(), "0 %")
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        after = dpn_employer_responsibility_from_saved_data(self._saved_data(accident.id))
        self.assertEqual(after[RESP_PROPOSED_PERCENT], 70)
        self.assertEqual(after[RESP_RECOGNIZED_PERCENT], 100)
        self.assertEqual(after[RESP_NOTE], "Dohoda bez částek")
        self.assertNotIn("reduction", after)


if __name__ == "__main__":
    unittest.main()
