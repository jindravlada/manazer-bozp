import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    import core.services.editable_catalog_service as editable_catalog_module

    importlib.reload(editable_catalog_module)

    from moduly.audity.constants import (
        AUDIT_PROGRAM_BUTTON_LABEL,
        AUDIT_PROGRAM_STATUS_OVERVIEW_REFRESHED,
        AUDIT_PROGRAM_STATUS_PROCESSES_DISTRIBUTED,
        AUDIT_PROGRAM_STATUS_PROGRAM_CREATED,
        AUDIT_PROGRAM_STATUS_VISIT_CREATED,
        AUDIT_PROGRAM_STATUS_VISITS_GENERATED,
        AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS,
        AUDIT_PROGRAM_WINDOW_TITLE,
        AUDIT_STANDARD_ISO_45001,
        AUDIT_STANDARD_ISO_9001,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.ui.audit_program_plan_tree_widget import (
        NODE_PROCESS,
        NODE_VISIT,
        NODE_WORKPLACE,
    )
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog

    from moduly.nastaveni.sluzby.settings_service import settings_service


class AuditProgramManagerDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        self._workplace = settings_service.save_workplace(
            name="Testovací provoz",
            address="",
            note="",
            active=True,
        )

    def _create_dialog(self) -> AuditProgramManagerDialog:
        dialog = AuditProgramManagerDialog()
        dialog.showMaximized()
        QApplication.processEvents()
        return dialog

    def test_dialog_opens_maximized(self) -> None:
        dialog = self._create_dialog()
        self.assertEqual(dialog.windowTitle(), AUDIT_PROGRAM_WINDOW_TITLE)
        self.assertTrue(dialog.isMaximized())
        self.assertGreaterEqual(dialog._program_list.count(), 0)

    def test_create_program_refreshes_list(self) -> None:
        dialog = self._create_dialog()
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.AuditProgramCreateDialog"
        ) as mock_dialog_cls:
            mock_dialog = mock_dialog_cls.return_value
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.program_payload.return_value = {
                "name": "Program auditů 2026–2029",
                "date_from": date(2026, 4, 1),
                "date_to": date(2029, 3, 31),
                "standards": [AUDIT_STANDARD_ISO_45001, AUDIT_STANDARD_ISO_9001],
                "description": "",
                "note": "",
            }
            dialog._create_program()

        self.assertGreaterEqual(dialog._program_list.count(), 1)
        self.assertEqual(dialog._status_label.text(), AUDIT_PROGRAM_STATUS_PROGRAM_CREATED)
        self.assertEqual(dialog._program_title_label.text(), "Program auditů 2026–2029")

    def test_load_program_list(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2029–2032",
            date_from=date(2029, 4, 1),
            date_to=date(2032, 3, 31),
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)

        self.assertGreaterEqual(dialog._program_list.count(), 1)
        self.assertEqual(
            dialog._program_list.currentItem().text(),
            "Program auditů 2029–2032",
        )

    def test_generate_visits_and_distribute_processes(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=6,
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)

        with patch.object(
            audit_program_service,
            "sync_workplaces_from_settings",
            return_value=0,
        ):
            dialog._generate_visits_btn.click()
        QApplication.processEvents()
        self.assertEqual(dialog._status_label.text(), AUDIT_PROGRAM_STATUS_VISITS_GENERATED)
        self.assertEqual(dialog._visit_count_value.text(), "0 / 6")

        dialog._distribute_processes_btn.click()
        QApplication.processEvents()
        self.assertEqual(
            dialog._status_label.text(),
            AUDIT_PROGRAM_STATUS_PROCESSES_DISTRIBUTED,
        )
        self.assertEqual(dialog._plan_tree.topLevelItemCount(), 1)
        workplace_item = dialog._plan_tree.topLevelItem(0)
        self.assertGreater(workplace_item.childCount(), 0)
        visit_item = workplace_item.child(0)
        self.assertGreater(visit_item.childCount(), 0)

    def test_refresh_overview(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=6,
        )
        audit_program_service.generate_visits(program.id)

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        dialog._refresh_overview_btn.click()
        QApplication.processEvents()

        self.assertEqual(dialog._status_label.text(), AUDIT_PROGRAM_STATUS_OVERVIEW_REFRESHED)
        self.assertGreaterEqual(dialog._plan_tree.topLevelItemCount(), 1)
        self.assertEqual(dialog._completion_value.text(), "0 %")
        workplace_names = {
            dialog._plan_tree.topLevelItem(row).text(0)
            for row in range(dialog._plan_tree.topLevelItemCount())
        }
        self.assertIn(self._workplace.name, workplace_names)

    def test_create_visit_from_tree(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=6,
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        workplace_item = dialog._plan_tree.topLevelItem(0)
        dialog._plan_tree.setCurrentItem(workplace_item)

        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.AuditProgramVisitDialog"
        ) as mock_dialog_cls:
            mock_dialog = mock_dialog_cls.return_value
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.visit_payload.return_value = {
                "planned_month": 5,
                "planned_year": 2026,
                "planned_date": date(2026, 5, 12),
                "note": "Ruční plán",
            }
            dialog._create_visit_for_selection()

        QApplication.processEvents()
        self.assertEqual(dialog._status_label.text(), AUDIT_PROGRAM_STATUS_VISIT_CREATED)
        self.assertEqual(dialog._plan_tree.topLevelItem(0).childCount(), 1)
        self.assertIn("Květen 2026", dialog._plan_tree.topLevelItem(0).child(0).text(0))
        self.assertIn("12. 5. 2026", dialog._plan_tree.topLevelItem(0).child(0).text(0))

    def test_plan_tree_action_states(self) -> None:
        from moduly.audity.ui.audit_program_plan_tree_widget import AuditProgramPlanTreeWidget

        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace.id,
            planned_year=2026,
            planned_month=4,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="dokumentace",
            process_name="Dokumentace",
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)

        workplace_item = dialog._plan_tree.topLevelItem(0)
        visit_item = workplace_item.child(0)
        process_item = visit_item.child(0)

        dialog._plan_tree.setCurrentItem(workplace_item)
        QApplication.processEvents()
        self.assertTrue(dialog._add_visit_btn.isEnabled())
        self.assertFalse(dialog._edit_visit_btn.isEnabled())
        self.assertFalse(dialog._move_process_btn.isEnabled())

        dialog._plan_tree.setCurrentItem(visit_item)
        QApplication.processEvents()
        self.assertFalse(dialog._add_visit_btn.isEnabled())
        self.assertTrue(dialog._edit_visit_btn.isEnabled())
        self.assertFalse(dialog._move_process_btn.isEnabled())

        dialog._plan_tree.setCurrentItem(process_item)
        QApplication.processEvents()
        self.assertFalse(dialog._add_visit_btn.isEnabled())
        self.assertTrue(dialog._move_process_btn.isEnabled())
        self.assertEqual(
            AuditProgramPlanTreeWidget.node_type(process_item),
            NODE_PROCESS,
        )
        self.assertEqual(
            AuditProgramPlanTreeWidget.node_type(visit_item),
            NODE_VISIT,
        )
        self.assertEqual(
            AuditProgramPlanTreeWidget.node_type(workplace_item),
            NODE_WORKPLACE,
        )

    def test_start_audit_action_enabled_for_planned_visit(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace.id,
            planned_year=2026,
            planned_month=4,
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        visit_item = dialog._plan_tree.topLevelItem(0).child(0)
        dialog._plan_tree.setCurrentItem(visit_item)
        QApplication.processEvents()

        self.assertTrue(dialog._start_audit_btn.isEnabled())
        self.assertFalse(dialog._open_audit_btn.isEnabled())

    def test_open_audit_action_after_visit_linked(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace.id,
            planned_year=2026,
            planned_month=4,
        )
        audit_program_service.create_audit_from_visit(visit.id)

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        visit_item = dialog._plan_tree.topLevelItem(0).child(0)
        dialog._plan_tree.setCurrentItem(visit_item)
        QApplication.processEvents()

        self.assertFalse(dialog._start_audit_btn.isEnabled())
        self.assertTrue(dialog._open_audit_btn.isEnabled())
        self.assertIn("▶", visit_item.text(0))

    def test_manager_has_dashboard_tabs(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        QApplication.processEvents()

        self.assertEqual(
            dialog._dashboard_widget._tabs.tabText(0),
            AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS,
        )
        self.assertTrue(dialog._dashboard_widget.isEnabled())


class AudityPageProgramButtonTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_audity_page_has_program_button(self) -> None:
        from moduly.audity.ui.audity_page import AudityPage

        page = AudityPage()
        self.assertTrue(hasattr(page, "program_btn"))
        self.assertEqual(page.program_btn.text(), AUDIT_PROGRAM_BUTTON_LABEL)

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_open_program_manager_opens_dialog(self, mock_exec) -> None:
        from moduly.audity.ui.audity_page import AudityPage

        page = AudityPage()
        page.open_program_manager()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertIsInstance(dialog, AuditProgramManagerDialog)
        self.assertEqual(dialog.windowTitle(), AUDIT_PROGRAM_WINDOW_TITLE)


if __name__ == "__main__":
    unittest.main()
