import importlib
import tempfile
import unittest
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
        FINDING_STATUS_V_PROCESU,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_service import audit_service


class AudityFindingsTaskTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_finding(self, audit_id: int) -> int:
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit_id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Testovací zjištění",
            recommended_action="Doplnit dokumentaci",
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding.id

    def test_create_task_from_finding_links_task(self) -> None:
        audit = audit_service.create_audit()
        finding_id = self._create_finding(audit.id)

        self.assertEqual(finding_task_service.get_task_action(finding_id), "create")

        task = finding_task_service.create_task_from_finding(finding_id)
        finding = finding_service.get_by_id(finding_id)

        assert finding is not None
        self.assertEqual(finding.task_id, task.id)
        self.assertEqual(finding.status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(task.source_record_id, finding_id)

    def test_reload_finding_offers_open_task_action(self) -> None:
        audit = audit_service.create_audit()
        finding_id = self._create_finding(audit.id)
        task = finding_task_service.create_task_from_finding(finding_id)

        reloaded = finding_service.get_by_id(finding_id)
        assert reloaded is not None
        self.assertEqual(reloaded.task_id, task.id)
        self.assertEqual(finding_task_service.get_task_action(reloaded.id), "open")

        linked_task = finding_task_service.get_linked_task(reloaded)
        assert linked_task is not None
        self.assertEqual(linked_task.id, task.id)

    def test_findings_widget_task_action_state(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget

        audit = audit_service.create_audit()
        finding_id = self._create_finding(audit.id)

        widget = AuditFindingsWidget()
        widget.set_audit_id(audit.id)
        self.assertEqual(widget.table.rowCount(), 1)

        index = widget.table.model().index(0, 0)
        widget.table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        widget.task_actions.update_state()

        self.assertEqual(widget._selected_finding_id(), finding_id)
        self.assertEqual(widget.task_actions._action, "create")
        self.assertFalse(widget.task_actions.button.isHidden())

        finding_task_service.create_task_from_finding(finding_id)
        widget.refresh()
        widget.table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        widget.task_actions.update_state()

        self.assertEqual(widget.task_actions._action, "open")
        self.assertEqual(widget.task_actions.button.text(), "Otevřít úkol")

    def test_findings_widget_edit_and_delete_still_available(self) -> None:
        from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget

        audit = audit_service.create_audit()
        finding_id = self._create_finding(audit.id)

        widget = AuditFindingsWidget()
        widget.set_audit_id(audit.id)

        self.assertTrue(widget.edit_btn.isEnabled())
        self.assertTrue(widget.delete_btn.isEnabled())
        self.assertTrue(hasattr(widget, "task_actions"))

        finding_service.delete(finding_id)
        widget.refresh()
        self.assertEqual(widget.table.rowCount(), 0)

    @patch("core.widgets.finding_task_actions.TaskDialog")
    def test_create_task_opens_task_dialog(self, mock_task_dialog) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget

        audit = audit_service.create_audit()
        finding_id = self._create_finding(audit.id)

        widget = AuditFindingsWidget()
        widget.set_audit_id(audit.id)
        index = widget.table.model().index(0, 0)
        widget.table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        widget.task_actions.update_state()
        widget.task_actions._create_task(finding_id)

        mock_task_dialog.assert_called_once()
        finding = finding_service.get_by_id(finding_id)
        assert finding is not None
        self.assertIsNotNone(finding.task_id)


if __name__ == "__main__":
    unittest.main()
