"""PU-DPN-7b – termín mimořádné prohlídky jako automatická povinnost."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QCalendarWidget, QToolButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-7b-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.nullable_date_edit import NullableDateEdit
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_dpn_care import (
        CARE_EXAM_DEADLINE,
        RETURN_MODE_SAME,
        exam_deadline_from_return_date,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import (
        EXAM_DEADLINE_NEED_RETURN,
        EXAM_DEADLINE_UNTIL_LABEL,
    )
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
RETURN_MONDAY = date(2026, 4, 20)
RETURN_AFTER_MAY_DAY = date(2026, 4, 28)


class PuDpn7bTestCase(unittest.TestCase):
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

    def _open_required(self):
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.severe_consequences_ano.setChecked(True)
        return accident, dialog, tab

    def test_return_date_is_before_exam_completion_fields(self) -> None:
        accident, dialog, tab = self._open_required()
        care_layout = tab.section_groups[1].layout()
        self.assertIs(care_layout.itemAt(1).widget(), tab._return_date_widget)
        self.assertIs(care_layout.itemAt(2).widget(), tab._exam_followup_widget)
        self.assertIs(care_layout.itemAt(3).widget(), tab._return_mode_widget)
        dialog.close()

    def test_deadline_computed_after_return_date(self) -> None:
        accident, dialog, tab = self._open_required()
        self.assertEqual(tab.exam_deadline_label.text(), EXAM_DEADLINE_NEED_RETURN)
        self.assertNotIn("27.04.2026", tab.exam_deadline_label.text())
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertEqual(
            tab.get_dpn_care_return()[CARE_EXAM_DEADLINE],
            exam_deadline_from_return_date(RETURN_MONDAY),
        )
        self.assertIn(EXAM_DEADLINE_UNTIL_LABEL, tab.exam_deadline_label.text())
        self.assertIn("27.04.2026", tab.exam_deadline_label.text())
        dialog.close()

    def test_deadline_is_not_editable(self) -> None:
        accident, dialog, tab = self._open_required()
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertFalse(hasattr(tab, "exam_deadline") and isinstance(tab.exam_deadline, NullableDateEdit))
        self.assertEqual(tab.exam_deadline_panel.findChildren(NullableDateEdit), [])
        self.assertEqual(tab.exam_deadline_panel.findChildren(QToolButton), [])
        self.assertEqual(tab.exam_deadline_panel.findChildren(QCalendarWidget), [])
        original = tab.exam_deadline_label.text()
        tab.exam_deadline_label.setText("1.1.1999")
        tab._refresh_care_relevance()
        self.assertEqual(tab.exam_deadline_label.text(), original)
        self.assertIn("27.04.2026", tab.exam_deadline_label.text())
        dialog.close()

    def test_changing_return_date_recomputes_deadline(self) -> None:
        accident, dialog, tab = self._open_required()
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertIn("27.04.2026", tab.exam_deadline_label.text())
        tab.return_date.set_date_value(RETURN_AFTER_MAY_DAY)
        expected = date.fromisoformat(exam_deadline_from_return_date(RETURN_AFTER_MAY_DAY))
        self.assertIn(expected.strftime("%d.%m.%Y"), tab.exam_deadline_label.text())
        self.assertNotIn("27.04.2026", tab.exam_deadline_label.text())
        self.assertEqual(
            tab.get_dpn_care_return()[CARE_EXAM_DEADLINE],
            "2026-05-06",
        )
        dialog.close()

    def test_missing_return_date_shows_prompt(self) -> None:
        accident, dialog, tab = self._open_required()
        self.assertFalse(tab._exam_followup_widget.isHidden())
        self.assertEqual(tab.exam_deadline_label.text(), EXAM_DEADLINE_NEED_RETURN)
        self.assertNotIn(EXAM_DEADLINE_UNTIL_LABEL, tab.exam_deadline_label.text())
        dialog.close()

    def test_deadline_hidden_when_exam_not_required(self) -> None:
        accident = self._create()
        dialog = AccidentDialog(accident=accident)
        tab = dialog.tab_po_ukonceni_dpn_widget
        tab.return_mode.setCurrentIndex(tab.return_mode.findData(RETURN_MODE_SAME))
        tab.return_date.set_date_value(RETURN_MONDAY)
        self.assertTrue(tab._exam_followup_widget.isHidden())
        self.assertFalse(tab.exam_date.isEnabled())
        self.assertFalse(tab.exam_result.isEnabled())
        self.assertIsNone(tab.get_dpn_care_return()[CARE_EXAM_DEADLINE])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
