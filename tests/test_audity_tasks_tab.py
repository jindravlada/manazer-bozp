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
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.ukoly.sluzby.task_service import task_service


class AudityTasksTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_finding(self, audit_id: int, *, description: str) -> int:
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit_id,
            finding_type=FINDING_TYPE_NESHODA,
            description=description,
            recommended_action=description,
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding.id

    def test_get_tasks_for_audit_empty(self) -> None:
        audit = audit_service.create_audit()

        tasks = audit_service.get_tasks_for_audit(audit.id)

        self.assertEqual(tasks, [])

    def test_get_tasks_for_audit_returns_linked_tasks(self) -> None:
        audit = audit_service.create_audit()
        finding1_id = self._create_finding(audit.id, description="První zjištění")
        finding2_id = self._create_finding(audit.id, description="Druhé zjištění")

        task1 = finding_task_service.create_task_from_finding(finding1_id)
        task2 = finding_task_service.create_task_from_finding(finding2_id)

        tasks = audit_service.get_tasks_for_audit(audit.id)

        self.assertEqual(len(tasks), 2)
        self.assertEqual({task.id for task in tasks}, {task1.id, task2.id})

    def test_tasks_widget_empty_state(self) -> None:
        from moduly.audity.ui.audit_tasks_widget import AuditTasksWidget

        audit = audit_service.create_audit()
        widget = AuditTasksWidget()
        widget.set_audit_id(audit.id)

        self.assertEqual(widget.table.rowCount(), 0)
        self.assertEqual(widget.content_stack.currentIndex(), 0)
        self.assertEqual(widget.empty_label.text(), "Audit zatím nemá žádné úkoly.")

    def test_tasks_widget_lists_and_refreshes_after_update(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from moduly.audity.ui.audit_tasks_widget import AuditTasksWidget

        audit = audit_service.create_audit()
        finding1_id = self._create_finding(audit.id, description="První zjištění")
        finding2_id = self._create_finding(audit.id, description="Druhé zjištění")
        task1 = finding_task_service.create_task_from_finding(finding1_id)
        finding_task_service.create_task_from_finding(finding2_id)

        widget = AuditTasksWidget()
        widget.set_audit_id(audit.id)

        self.assertEqual(widget.table.rowCount(), 2)
        self.assertEqual(widget.content_stack.currentIndex(), 1)

        task_service.update_task(
            task_id=task1.id,
            title=task1.title,
            description=task1.description,
            priority=task1.priority,
            due_date=date(2026, 8, 20),
            responsible_person_id=task1.responsible_person_id,
            workplace_id=task1.workplace_id,
            completed=task1.completed,
            completed_date=task1.completed_date,
            requires_verification=task1.requires_verification,
            check_due_date=task1.check_due_date,
            checked_date=task1.checked_date,
            checked_by_id=task1.checked_by_id,
            canceled=task1.canceled,
            note=task1.note,
        )

        widget.refresh()

        due_dates = {
            widget.table.item(row, 3).text()
            for row in range(widget.table.rowCount())
        }
        self.assertIn("20.08.2026", due_dates)

        index = widget.table.model().index(0, 0)
        widget.table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        self.assertEqual(widget._selected_task_id(), task1.id)


if __name__ == "__main__":
    unittest.main()
