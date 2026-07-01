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
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service


class ProverkyTasksTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_finding(self, inspection_id: int, *, description: str) -> int:
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection_id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description=description,
            recommended_action=description,
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding.id

    def test_get_tasks_for_inspection_empty(self) -> None:
        inspection = bozp_inspection_service.create_inspection()

        tasks = bozp_inspection_service.get_tasks_for_inspection(inspection.id)

        self.assertEqual(tasks, [])

    def test_get_tasks_for_inspection_returns_linked_tasks(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        finding1_id = self._create_finding(inspection.id, description="První zjištění")
        finding2_id = self._create_finding(inspection.id, description="Druhé zjištění")

        task1 = finding_task_service.create_task_from_finding(finding1_id)
        task2 = finding_task_service.create_task_from_finding(finding2_id)

        tasks = bozp_inspection_service.get_tasks_for_inspection(inspection.id)

        self.assertEqual(len(tasks), 2)
        self.assertEqual({task.id for task in tasks}, {task1.id, task2.id})

    def test_tasks_widget_empty_state(self) -> None:
        from moduly.proverky.ui.bozp_inspection_tasks_widget import BozpInspectionTasksWidget

        inspection = bozp_inspection_service.create_inspection()
        widget = BozpInspectionTasksWidget()
        widget.set_inspection_id(inspection.id)

        self.assertEqual(widget.table.rowCount(), 0)
        self.assertEqual(widget.content_stack.currentIndex(), 0)
        self.assertEqual(widget.empty_label.text(), "Prověrka zatím nemá žádné úkoly.")

    def test_tasks_widget_lists_and_refreshes_after_update(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from moduly.proverky.ui.bozp_inspection_tasks_widget import BozpInspectionTasksWidget

        inspection = bozp_inspection_service.create_inspection()
        finding1_id = self._create_finding(inspection.id, description="První zjištění")
        finding2_id = self._create_finding(inspection.id, description="Druhé zjištění")
        task1 = finding_task_service.create_task_from_finding(finding1_id)
        finding_task_service.create_task_from_finding(finding2_id)

        widget = BozpInspectionTasksWidget()
        widget.set_inspection_id(inspection.id)

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
