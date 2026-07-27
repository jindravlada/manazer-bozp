"""KU-UX-12 – logika druhu pracovního úrazu a pracovní neschopnosti."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="ku-ux-12-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import ENTITY_ACCIDENT
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        DPN_END_BEFORE_START_MESSAGE,
        DPN_END_IN_FUTURE_MESSAGE,
        DPN_KIND_MISMATCH_BLOCK_MESSAGE,
        DPN_START_BEFORE_ACCIDENT_MESSAGE,
        is_dpn_end_before_start,
        is_dpn_end_in_future,
        is_dpn_kind_mismatch,
        is_dpn_start_before_accident,
        is_no_pn_kind,
    )
    from moduly.kniha_urazu.sluzby.accident_service import (
        verify_accident_kind_task_title,
        accident_service,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.ukoly.sluzby.task_service import task_service


KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_NO_PN = "Bez pracovní neschopnosti"


class KuUx12TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(Accident))
            session.commit()

    def _bypass_required_validation(self, dialog: AccidentDialog) -> None:
        for tab in (
            dialog.tab_podatel_widget,
            dialog.tab_zamestnanec_widget,
            dialog.tab_uraz_widget,
            dialog.tab_pracoviste_widget,
            dialog.tab_dalsi_widget,
            dialog.tab_svedci_widget,
        ):
            if hasattr(tab, "validate"):
                tab.validate = MagicMock(return_value=[])

    def test_dpn_date_helpers(self) -> None:
        accident = date(2026, 3, 10)
        self.assertTrue(is_dpn_start_before_accident(date(2026, 3, 9), accident))
        self.assertFalse(is_dpn_start_before_accident(date(2026, 3, 10), accident))
        self.assertTrue(is_dpn_end_before_start(date(2026, 3, 12), date(2026, 3, 11)))
        self.assertFalse(is_dpn_end_before_start(date(2026, 3, 12), date(2026, 3, 12)))
        self.assertTrue(is_dpn_end_in_future(date.today() + timedelta(days=1)))
        self.assertFalse(is_dpn_end_in_future(None))
        self.assertFalse(is_dpn_end_in_future(date.today()))

    def test_no_pn_kind_mismatch_when_dpn_days_known(self) -> None:
        self.assertTrue(is_no_pn_kind(KIND_NO_PN))
        self.assertTrue(is_dpn_kind_mismatch(KIND_NO_PN, 2))
        self.assertFalse(is_dpn_kind_mismatch(KIND_NO_PN, None))
        self.assertFalse(is_dpn_kind_mismatch(KIND_UP_TO_3, 2))
        self.assertFalse(is_dpn_kind_mismatch(KIND_OVER_3, None))

    def test_dpn_start_before_accident_blocks_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(date(2026, 4, 10).isoformat())
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date(2026, 4, 8))

        with patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(QDialog, "accept") as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertIn(DPN_START_BEFORE_ACCIDENT_MESSAGE, mock_warning.call_args.args[2])

    def test_dpn_end_before_start_blocks_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(date(2026, 4, 1).isoformat())
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date(2026, 4, 5))
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 4, 3))

        with patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(QDialog, "accept") as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertIn(DPN_END_BEFORE_START_MESSAGE, mock_warning.call_args.args[2])

    def test_dpn_end_in_future_blocks_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(date.today().isoformat())
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date.today())
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date.today() + timedelta(days=2))

        with patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(QDialog, "accept") as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertIn(DPN_END_IN_FUTURE_MESSAGE, mock_warning.call_args.args[2])

    def test_ongoing_dpn_without_end_allows_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(date.today().isoformat())
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(date.today())
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date.today())
        # dpn_do zůstává prázdné

        with patch.object(QDialog, "accept") as mock_accept:
            dialog.accept()

        mock_accept.assert_called_once()

    def test_known_dpn_over_3_with_up_to_3_kind_blocks_save(self) -> None:
        dialog = AccidentDialog()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(date(2026, 5, 1).isoformat())
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(date(2026, 5, 1))
        dialog.tab_uraz_widget.druh_urazu.set_value(KIND_UP_TO_3)
        dialog.tab_zamestnanec_widget.dpn_od.set_date_value(date(2026, 5, 1))
        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 5, 10))

        with patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(QDialog, "accept") as mock_accept:
                dialog.accept()

        mock_accept.assert_not_called()
        self.assertIn(DPN_KIND_MISMATCH_BLOCK_MESSAGE, mock_warning.call_args.args[2])

    def test_create_accident_creates_verify_kind_task(self) -> None:
        accident_date = date.today()
        accident = accident_service.create_accident(
            jmeno_prijmeni="Jan Novák",
            accident_date=accident_date,
            year=accident_date.year,
            druh_urazu=(
                "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
            ),
            dpn_od=accident_date,
        )

        tasks = [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT and task.source_record_id == accident.id
        ]
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task.title, verify_accident_kind_task_title(accident.number))
        self.assertEqual(task.due_date, accident_date + timedelta(days=5))
        self.assertIn(f"č. {accident.number}", task.description)
        self.assertIn("upravit druh pracovního úrazu", task.description)


if __name__ == "__main__":
    unittest.main()
