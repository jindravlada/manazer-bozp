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
        DEFAULT_INSPECTION_SPIS_STATUS,
        INSPECTION_COMPLETION_CONFIRM_MESSAGE,
        INSPECTION_STATUS_DOKONCENO,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


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
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        inspection = bozp_inspection_service.create_inspection()
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": workplace_id,
                    "display_name": "Eva Králová",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
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

    def _open_dialog(self, inspection):
        from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog

        return BozpInspectionDialog(inspection=inspection)

    def test_dialog_last_tab_is_zaver(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        dialog = self._open_dialog(inspection)

        self.assertEqual(dialog.tabs.tabText(dialog.tabs.count() - 1), "Závěr")

    def test_dialog_has_no_attachments_tab(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        dialog = self._open_dialog(inspection)

        tab_labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertNotIn("Přílohy", tab_labels)

    def test_spis_has_no_status_editor(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        dialog = self._open_dialog(inspection)

        self.assertFalse(hasattr(dialog.spis_widget, "status_combo"))
        self.assertFalse(hasattr(dialog.spis_widget, "finished_at_edit"))

    def test_get_conclusion_summary(self) -> None:
        inspection, _ = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_task_service.create_task_from_finding(finding_id)

        summary = bozp_inspection_service.get_conclusion_summary(inspection.id)

        self.assertEqual(summary["findings_total"], 1)
        self.assertEqual(summary["findings_open"], 1)
        self.assertEqual(summary["tasks_total"], 1)
        self.assertEqual(summary["tasks_active"], 1)

    def test_get_completion_blockers_empty(self) -> None:
        inspection, _ = self._create_inspection_with_leader()

        blockers = bozp_inspection_service.get_completion_blockers(inspection.id)

        self.assertFalse(blockers.has_blockers())

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_complete_without_blockers_saves_completed(self, mock_question) -> None:
        inspection, _ = self._create_inspection_with_leader()
        dialog = self._open_dialog(inspection)

        dialog.conclusion_widget._complete_inspection()

        mock_question.assert_not_called()
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, INSPECTION_STATUS_DOKONCENO)
        self.assertEqual(loaded.finished_at, date.today())
        self.assertEqual(dialog.conclusion_widget.status_label.text(), INSPECTION_STATUS_DOKONCENO)

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_complete_with_blockers_cancel_keeps_incomplete(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, _ = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection)
        mock_question.return_value = QMessageBox.No

        dialog.conclusion_widget._complete_inspection()

        mock_question.assert_called_once()
        self.assertEqual(
            mock_question.call_args.args[2],
            INSPECTION_COMPLETION_CONFIRM_MESSAGE,
        )
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, DEFAULT_INSPECTION_SPIS_STATUS)

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_complete_with_blockers_confirm_saves_completed(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, _ = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection)
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_inspection()

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, INSPECTION_STATUS_DOKONCENO)

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_confirm_completion_sets_finished_at_when_empty(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, _ = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.finished_at_edit.clear_date()
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_inspection()

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.finished_at, date.today())

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_confirm_completion_keeps_existing_finished_at(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, _ = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_task_service.create_task_from_finding(finding_id)
        dialog = self._open_dialog(inspection)
        existing_date = date(2026, 4, 15)
        dialog.conclusion_widget.finished_at_edit.set_date_value(existing_date)
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_inspection()

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.finished_at, existing_date)

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_active_task_triggers_confirmation(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, _ = self._create_inspection_with_leader()
        finding_id = self._create_open_finding(inspection.id)
        finding_task_service.create_task_from_finding(finding_id)
        finding_service.update(finding_id, status=FINDING_STATUS_VYPORADANO)
        dialog = self._open_dialog(inspection)
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_inspection()

        mock_question.assert_called_once()

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_completed_state_persists_after_reopen(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        inspection, _ = self._create_inspection_with_leader()
        self._create_open_finding(inspection.id)
        dialog = self._open_dialog(inspection)
        mock_question.return_value = QMessageBox.Yes
        dialog.conclusion_widget._complete_inspection()

        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        assert reloaded is not None

        dialog2 = self._open_dialog(reloaded)
        self.assertEqual(dialog2.conclusion_widget.status_label.text(), INSPECTION_STATUS_DOKONCENO)
        self.assertEqual(
            dialog2.conclusion_widget.finished_at_edit.get_date(),
            reloaded.finished_at,
        )
        self.assertFalse(dialog2.conclusion_widget.complete_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
