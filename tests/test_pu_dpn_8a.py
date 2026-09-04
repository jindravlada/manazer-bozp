"""PU-DPN-8a – krácení náhrady na stejném řádku jako rozsah."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-8a-"))

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
    from moduly.kniha_urazu.sluzby.accident_dpn_responsibility import reduction_percent
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import LABEL_REDUCTION
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


class PuDpn8aTestCase(unittest.TestCase):
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

    def _open(self):
        accident = accident_service.create_accident(
            jmeno_prijmeni="Jan Novák",
            pohlavi="Muž",
            datum_narozeni=date(1990, 1, 1),
            druh_urazu=KIND_OVER_3,
            accident_date=date(2026, 4, 1),
            accident_time="10:00",
            popis_urazoveho_deje="Pád z žebříku",
            dpn_od=date(2026, 4, 1),
            dpn_do=date(2026, 4, 20),
            opatreni="Kontrola žebříků",
            zranena_cast_tela="Levé zápěstí",
        )
        dialog = AccidentDialog(accident=accident)
        return dialog, dialog.tab_po_ukonceni_dpn_widget

    def test_reduction_shares_row_with_percent(self) -> None:
        dialog, tab = self._open()
        proposed_row = tab.proposed_percent.parentWidget()
        recognized_row = tab.recognized_percent.parentWidget()
        self.assertIs(proposed_row, tab.proposed_reduction_label.parentWidget())
        self.assertIs(recognized_row, tab.recognized_reduction_label.parentWidget())
        self.assertIsInstance(proposed_row.layout(), QHBoxLayout)
        self.assertIsInstance(recognized_row.layout(), QHBoxLayout)
        self.assertIsNot(proposed_row, tab.responsibility_note.parentWidget())
        tab.proposed_percent.setValue(60)
        tab.recognized_percent.setValue(50)
        self.assertEqual(tab.proposed_reduction_caption.text(), LABEL_REDUCTION)
        self.assertEqual(tab.proposed_reduction_label.text(), "40 %")
        self.assertEqual(tab.recognized_reduction_label.text(), "50 %")
        self.assertEqual(reduction_percent(60), 40)
        self.assertEqual(
            tab.proposed_reduction_label.textInteractionFlags(),
            Qt.TextInteractionFlag.NoTextInteraction,
        )
        dialog.close()

    def test_note_stays_full_width_below(self) -> None:
        dialog, tab = self._open()
        form = tab._responsibility_form
        note_row = None
        proposed_row = None
        for index in range(form.rowCount()):
            field = form.itemAt(index, form.ItemRole.FieldRole)
            if field is None:
                continue
            widget = field.widget()
            if widget is tab.responsibility_note:
                note_row = index
            if widget is tab.proposed_percent.parentWidget():
                proposed_row = index
        self.assertIsNotNone(note_row)
        self.assertIsNotNone(proposed_row)
        self.assertGreater(note_row, proposed_row)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
