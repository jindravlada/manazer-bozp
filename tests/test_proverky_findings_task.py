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
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service


class ProverkyFindingsTaskTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_finding(self, inspection_id: int) -> int:
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection_id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Testovací zjištění",
            recommended_action="Doplnit OOPP",
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding.id

    def test_create_task_from_finding_links_task(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        finding_id = self._create_finding(inspection.id)

        self.assertEqual(finding_task_service.get_task_action(finding_id), "create")

        task = finding_task_service.create_task_from_finding(finding_id)
        finding = finding_service.get_by_id(finding_id)

        assert finding is not None
        self.assertEqual(finding.task_id, task.id)
        self.assertEqual(finding.status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(task.source_record_id, finding_id)

    def test_reload_finding_offers_open_task_action(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        finding_id = self._create_finding(inspection.id)
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

        from moduly.proverky.ui.bozp_inspection_findings_widget import (
            BozpInspectionFindingsWidget,
        )

        inspection = bozp_inspection_service.create_inspection()
        finding_id = self._create_finding(inspection.id)

        widget = BozpInspectionFindingsWidget()
        widget.set_inspection_id(inspection.id)
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
        from moduly.proverky.ui.bozp_inspection_findings_widget import (
            BozpInspectionFindingsWidget,
        )

        inspection = bozp_inspection_service.create_inspection()
        finding_id = self._create_finding(inspection.id)

        widget = BozpInspectionFindingsWidget()
        widget.set_inspection_id(inspection.id)

        self.assertTrue(widget.edit_btn.isEnabled())
        self.assertTrue(widget.delete_btn.isEnabled())
        self.assertTrue(hasattr(widget, "task_actions"))

        finding_service.delete(finding_id)
        widget.refresh()
        self.assertEqual(widget.table.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
