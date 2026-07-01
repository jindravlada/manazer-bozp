import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.proverky.constants import (
        INSPECTION_COMPLETION_CONFIRM_MESSAGE,
        INSPECTION_STATUS_DOKONCENO,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


class ProverkyCompletionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_leader(self) -> int:
        worker = settings_service.save_worker(first_name="Jan", last_name="Novák")
        return worker.id

    def _create_inspection_with_leader(self):
        leader_id = self._create_leader()
        inspection = bozp_inspection_service.create_inspection()
        return inspection, leader_id

    def _create_open_finding(self, inspection_id: int) -> int:
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection_id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Otevřené zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding.id

    def _open_dialog(self, inspection, leader_id):
        from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog

        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.commission_widget.leader_selector.set_person_id(leader_id)
        dialog.spis_widget.status_combo.setCurrentText(INSPECTION_STATUS_DOKONCENO)
        return dialog

    def test_get_completion_blockers_empty(self) -> None:
        inspection, _ = self._create_inspection_with_leader()

        blockers = bozp_inspection_service.get_completion_blockers(inspection.id)

        self.assertFalse(blockers.has_blockers())
        self.assertEqual(blockers.open_findings, [])
        self.assertEqual(blockers.active_tasks, [])

    def test_get_completion_blockers_with_open_finding(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)

        blockers = bozp_inspection_service.get_completion_blockers(inspection.id)

        self.assertTrue(blockers.has_blockers())
        self.assertEqual(len(blockers.open_findings), 1)

    def test_get_completion_blockers_with_active_task(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_task_service.create_task_from_finding(finding_id)

        blockers = bozp_inspection_service.get_completion_blockers(inspection.id)

        self.assertTrue(blockers.has_blockers())
        self.assertEqual(len(blockers.active_tasks), 1)

    def test_get_completion_blockers_ignores_resolved_finding(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_service.update(finding_id, status=FINDING_STATUS_VYPORADANO)

        blockers = bozp_inspection_service.get_completion_blockers(inspection.id)

        self.assertFalse(blockers.has_blockers())

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.question")
    def test_complete_without_blockers_skips_confirmation(self, mock_question) -> None:
        from PySide6.QtWidgets import QDialog

        inspection, leader_id = self._create_inspection_with_leader()
        dialog = self._open_dialog(inspection, leader_id)

        dialog.accept()

        mock_question.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.get_data()["status"], INSPECTION_STATUS_DOKONCENO)

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.question")
    def test_complete_with_blockers_cancel_keeps_dialog_open(self, mock_question) -> None:
        from PySide6.QtWidgets import QDialog, QMessageBox

        inspection, leader_id = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection, leader_id)
        mock_question.return_value = QMessageBox.No

        dialog.accept()

        mock_question.assert_called_once()
        self.assertEqual(
            mock_question.call_args.args[2],
            INSPECTION_COMPLETION_CONFIRM_MESSAGE,
        )
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.question")
    def test_complete_with_blockers_confirm_saves_completed(self, mock_question) -> None:
        from PySide6.QtWidgets import QDialog, QMessageBox

        inspection, leader_id = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection, leader_id)
        mock_question.return_value = QMessageBox.Yes

        dialog.accept()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.get_data()["status"], INSPECTION_STATUS_DOKONCENO)

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.question")
    def test_confirm_completion_sets_finished_at_when_empty(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, leader_id = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection, leader_id)
        dialog.spis_widget.finished_at_edit.clear_date()
        mock_question.return_value = QMessageBox.Yes

        dialog.accept()
        data = dialog.get_data()

        self.assertEqual(data["finished_at"], date.today())

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.question")
    def test_confirm_completion_keeps_existing_finished_at(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, leader_id = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_task_service.create_task_from_finding(finding_id)
        dialog = self._open_dialog(inspection, leader_id)
        existing_date = date(2026, 4, 15)
        dialog.spis_widget.finished_at_edit.set_date_value(existing_date)
        mock_question.return_value = QMessageBox.Yes

        dialog.accept()
        data = dialog.get_data()

        self.assertEqual(data["finished_at"], existing_date)

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.question")
    def test_active_task_triggers_confirmation(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, leader_id = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_task_service.create_task_from_finding(finding_id)
        finding_service.update(finding_id, status=FINDING_STATUS_VYPORADANO)
        dialog = self._open_dialog(inspection, leader_id)
        mock_question.return_value = QMessageBox.Yes

        dialog.accept()

        mock_question.assert_called_once()


if __name__ == "__main__":
    unittest.main()
