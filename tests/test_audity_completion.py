import importlib
import tempfile
import unittest
import uuid
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
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import (
        AUDIT_COMPLETION_CONFIRM_MESSAGE,
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PLANOVANO,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AudityCompletionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_audit_with_team(self):
        suffix = uuid.uuid4().hex[:6]
        leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"Novák-{suffix}"
        ).id
        workplace_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Králová-{suffix}"
        ).id
        union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Horáková-{suffix}"
        ).id
        audit = audit_service.create_audit()
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": workplace_id,
                    "display_name": "Eva Králová",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return audit

    def _create_open_finding(self, audit_id: int) -> int:
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit_id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding.id

    def _open_dialog(self, audit):
        from moduly.audity.ui.audit_dialog import AuditDialog

        return AuditDialog(audit=audit)

    def test_dialog_last_tab_is_zaver(self) -> None:
        audit = self._create_audit_with_team()
        dialog = self._open_dialog(audit)

        self.assertEqual(dialog.tabs.tabText(dialog.tabs.count() - 1), "Závěr")

    def test_spis_has_no_status_editor(self) -> None:
        audit = self._create_audit_with_team()
        dialog = self._open_dialog(audit)

        self.assertFalse(hasattr(dialog.spis_widget, "status_combo"))
        self.assertFalse(hasattr(dialog.spis_widget, "finished_at_edit"))

    def test_get_conclusion_summary(self) -> None:
        audit = self._create_audit_with_team()
        finding_id = self._create_open_finding(audit.id)
        finding_task_service.create_task_from_finding(finding_id)

        summary = audit_service.get_conclusion_summary(audit.id)

        self.assertEqual(summary["findings_total"], 1)
        self.assertEqual(summary["findings_open"], 1)
        self.assertEqual(summary["tasks_total"], 1)
        self.assertEqual(summary["tasks_active"], 1)

    def test_get_completion_blockers_empty(self) -> None:
        audit = self._create_audit_with_team()

        blockers = audit_service.get_completion_blockers(audit.id)

        self.assertFalse(blockers.has_blockers())

    def _fill_conclusion(self, dialog, text: str = "Závěr testovacího auditu.") -> None:
        from moduly.audity.sluzby.audit_lead_recommendation_service import (
            generate_lead_auditor_recommendation,
        )

        dialog.conclusion_widget.conclusion_edit.setPlainText(text)
        dialog.conclusion_widget.recommendation_edit.setPlainText(
            generate_lead_auditor_recommendation(dialog.audit.id)
        )
        self.assertTrue(dialog._persist())

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_complete_without_blockers_saves_completed(self, mock_question) -> None:
        audit = self._create_audit_with_team()
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)

        dialog.conclusion_widget._complete_audit()

        mock_question.assert_not_called()
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.status, AUDIT_STATUS_DOKONCENO)
        self.assertEqual(loaded.finished_at, date.today())
        self.assertEqual(dialog.conclusion_widget.status_label.text(), AUDIT_STATUS_DOKONCENO)

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_complete_with_blockers_cancel_keeps_incomplete(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit_with_team()
        self._create_open_finding(audit.id)
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)
        mock_question.return_value = QMessageBox.No

        dialog.conclusion_widget._complete_audit()

        mock_question.assert_called_once()
        self.assertEqual(
            mock_question.call_args.args[2],
            AUDIT_COMPLETION_CONFIRM_MESSAGE,
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.status, AUDIT_STATUS_PLANOVANO)

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_complete_with_blockers_confirm_saves_completed(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit_with_team()
        self._create_open_finding(audit.id)
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_audit()

        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.status, AUDIT_STATUS_DOKONCENO)

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_confirm_completion_sets_finished_at_when_empty(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit_with_team()
        self._create_open_finding(audit.id)
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)
        dialog.conclusion_widget.finished_at_edit.clear_date()
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_audit()

        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.finished_at, date.today())

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_confirm_completion_keeps_existing_finished_at(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit_with_team()
        finding_id = self._create_open_finding(audit.id)
        finding_task_service.create_task_from_finding(finding_id)
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)
        existing_date = date(2026, 4, 15)
        dialog.conclusion_widget.finished_at_edit.set_date_value(existing_date)
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_audit()

        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.finished_at, existing_date)

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_active_task_triggers_confirmation(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit_with_team()
        finding_id = self._create_open_finding(audit.id)
        finding_task_service.create_task_from_finding(finding_id)
        finding_service.update(finding_id, status=FINDING_STATUS_VYPORADANO)
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)
        mock_question.return_value = QMessageBox.Yes

        dialog.conclusion_widget._complete_audit()

        mock_question.assert_called_once()

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.question")
    def test_completed_state_persists_after_reopen(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit_with_team()
        self._create_open_finding(audit.id)
        dialog = self._open_dialog(audit)
        self._fill_conclusion(dialog)
        mock_question.return_value = QMessageBox.Yes
        dialog.conclusion_widget._complete_audit()

        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None

        dialog2 = self._open_dialog(reloaded)
        self.assertEqual(dialog2.conclusion_widget.status_label.text(), AUDIT_STATUS_DOKONCENO)
        self.assertEqual(
            dialog2.conclusion_widget.finished_at_edit.get_date(),
            reloaded.finished_at,
        )
        self.assertFalse(dialog2.conclusion_widget.complete_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
