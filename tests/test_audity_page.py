import importlib
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.navigation.source_navigator import source_navigator
    from core.shared.constants import ENTITY_AUDITY
    from moduly.audity.constants import (
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
        AUDIT_TYPE_RADNY,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        AUDIT_PROGRAM_BUTTON_LABEL,
        AUDIT_PROTOCOL_BUTTON_LABEL,
        AUDIT_DETAILED_REPORT_BUTTON_LABEL,
        DEFAULT_AUDIT_STATUS_FILTER,
        KNOWLEDGE_EDITOR_BUTTON_LABEL,
        KNOWLEDGE_EDITOR_WINDOW_TITLE,
        MODULE_NAME,
        YEAR_FILTER_VSE,
    )
    from moduly.audity.module import get_module_definition
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AudityPageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"Novák-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Králová-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Horáková-{suffix}"
        ).id

    def _create_page(self):
        from moduly.audity.ui.audity_page import AudityPage

        return AudityPage()

    def _commission_members(self) -> list[dict]:
        return [
            {
                "record_type": COMMISSION_RECORD_LEADER,
                "thp_worker_id": self.leader_id,
                "display_name": "Jan Novák",
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_WORKPLACE,
                "thp_worker_id": self.workplace_rep_id,
                "display_name": "Eva Králová",
                "display_order": 15,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_UNION,
                "person_id": self.union_id,
                "display_name": "Lucie Horáková",
                "display_order": 20,
                "active": True,
            },
        ]

    def test_module_definition_is_registered(self) -> None:
        module = get_module_definition()

        self.assertEqual(module.key, "audity")
        self.assertEqual(module.name, MODULE_NAME)
        self.assertTrue(module.enabled)

    def test_toolbar_has_core_actions(self) -> None:
        page = self._create_page()

        self.assertTrue(page.new_btn.isEnabled())
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.delete_btn.isEnabled())
        self.assertTrue(page.knowledge_editor_btn.isEnabled())
        self.assertFalse(hasattr(page, "refresh_btn"))
        self.assertEqual(page.knowledge_editor_btn.text(), KNOWLEDGE_EDITOR_BUTTON_LABEL)
        self.assertEqual(page.program_btn.text(), AUDIT_PROGRAM_BUTTON_LABEL)
        self.assertEqual(page.protocol_btn.text(), AUDIT_PROTOCOL_BUTTON_LABEL)
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertEqual(page.detailed_report_btn.text(), AUDIT_DETAILED_REPORT_BUTTON_LABEL)
        self.assertFalse(page.detailed_report_btn.isEnabled())
        self.assertTrue(hasattr(page, "report_btn"))
        self.assertFalse(hasattr(page, "plan_btn"))

    def test_protocol_action_enabled_only_for_completed_audit(self) -> None:
        planned = audit_service.create_audit()
        in_progress = audit_service.create_audit(started_at=date(2026, 3, 1))
        completed = audit_service.create_audit(
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )

        page = self._create_page()
        page.status_filter.setCurrentText("Vše")
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()

        by_id = {
            int(page.table.item(row, 0).text()): row
            for row in range(page.table.rowCount())
        }

        page.table.selectRow(by_id[planned.id])
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())

        page.table.selectRow(by_id[in_progress.id])
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())

        page.table.selectRow(by_id[completed.id])
        self.assertTrue(page.protocol_btn.isEnabled())
        self.assertTrue(page.detailed_report_btn.isEnabled())
        self.assertEqual(completed.status, AUDIT_STATUS_DOKONCENO)

    @patch("moduly.audity.ui.audity_page.protokol_audit_service.open_for_audit")
    def test_export_selected_protocol_opens_for_completed_audit(self, mock_open) -> None:
        audit = audit_service.create_audit(
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )
        page = self._create_page()
        page.status_filter.setCurrentText("Vše")
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        page.table.selectRow(0)

        page.export_selected_protocol()

        mock_open.assert_called_once()
        self.assertEqual(mock_open.call_args.args[0].id, audit.id)

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_open_knowledge_editor_opens_dialog(self, mock_exec) -> None:
        from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog

        page = self._create_page()
        page.open_knowledge_editor()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertIsInstance(dialog, AudityKnowledgeEditorDialog)
        self.assertEqual(dialog.windowTitle(), KNOWLEDGE_EDITOR_WINDOW_TITLE)
        self.assertGreaterEqual(dialog.knowledge_tree.topLevelItemCount(), 1)

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_open_program_manager_opens_dialog(self, mock_exec) -> None:
        from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog

        page = self._create_page()
        page.open_program_manager()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertIsInstance(dialog, AuditProgramManagerDialog)

    def test_table_columns(self) -> None:
        from PySide6.QtWidgets import QHeaderView

        page = self._create_page()

        self.assertEqual(
            [
                page.table.horizontalHeaderItem(column).text()
                for column in range(page.table.columnCount())
            ],
            [
                "ID",
                "Číslo auditu",
                "Rok",
                "Plánovaný měsíc",
                "Auditovaný provoz",
                "Datum auditu",
                "Stav",
                "Typ auditu",
            ],
        )
        header = page.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(4),
            QHeaderView.ResizeMode.Stretch,
        )

    def test_status_filter_defaults_to_probihajici(self) -> None:
        page = self._create_page()

        self.assertEqual(page.status_filter.currentText(), DEFAULT_AUDIT_STATUS_FILTER)

    def test_year_filter_shows_current_year_and_all(self) -> None:
        page = self._create_page()

        self.assertEqual(page.year_filter.itemText(0), str(date.today().year))
        self.assertEqual(page.year_filter.itemData(1), YEAR_FILTER_VSE)

    def test_filter_by_status(self) -> None:
        audit_service.create_audit(started_at=date(2026, 3, 1))
        audit_service.create_audit()
        audit_service.create_audit(
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )

        page = self._create_page()
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.status_filter.setCurrentText("Plánované")
        page.refresh()

        statuses = {
            page.table.item(row, 6).text()
            for row in range(page.table.rowCount())
        }
        self.assertEqual(statuses, {AUDIT_STATUS_PLANOVANO})

    def test_filter_by_year(self) -> None:
        audit_service.create_audit(year=2026, planned_month=4)
        audit_service.create_audit(year=2025, planned_month=6)

        page = self._create_page()
        page.status_filter.setCurrentText("Vše")
        page.year_filter.setCurrentIndex(page.year_filter.findData(2026))
        page.refresh()

        years = {
            page.table.item(row, 2).text()
            for row in range(page.table.rowCount())
        }
        self.assertEqual(years, {"2026"})

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_new_audit_adds_row_to_table(self, mock_exec) -> None:
        page = self._create_page()

        def _accept_dialog(dialog):
            dialog.spis_widget._set_year(2026)
            dialog.spis_widget.planned_month_combo.setCurrentIndex(4)
            dialog.spis_widget.audit_date_edit.set_date_value(date(2026, 4, 15))
            dialog.spis_widget.type_combo.setCurrentText(AUDIT_TYPE_RADNY)
            dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
            dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
            dialog.commission_widget.union_selector.set_person_id(self.union_id)
            return True

        mock_exec.side_effect = _accept_dialog
        page.status_filter.setCurrentText("Vše")
        page.new_audit()

        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 2).text(), "2026")
        self.assertEqual(page.table.item(0, 3).text(), "duben")
        self.assertEqual(page.table.item(0, 5).text(), "15.04.2026")
        self.assertEqual(page.table.item(0, 6).text(), AUDIT_STATUS_PLANOVANO)
        self.assertEqual(page.table.item(0, 7).text(), AUDIT_TYPE_RADNY)

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_open_audit_loads_existing_record(self, mock_exec) -> None:
        audit = audit_service.create_audit(
            year=2026,
            planned_month=5,
            audit_date=date(2026, 5, 20),
            audit_type=AUDIT_TYPE_RADNY,
            started_at=date(2026, 5, 10),
        )
        audit_commission_service.save_members(audit.id, self._commission_members())

        page = self._create_page()
        page.table.selectRow(0)

        captured = {}

        def _exec(dialog):
            captured["dialog"] = dialog
            return False

        mock_exec.side_effect = _exec
        page.open_selected_audit()

        dialog = captured["dialog"]
        self.assertEqual(dialog.spis_widget.year_combo.currentData(), 2026)
        self.assertEqual(dialog.spis_widget.planned_month_combo.currentData(), 5)
        self.assertEqual(dialog.spis_widget.audit_date_edit.get_date(), date(2026, 5, 20))
        self.assertEqual(dialog.spis_widget.status_label.text(), AUDIT_STATUS_PROBIHA)
        self.assertEqual(dialog.commission_widget.leader_selector.current_person_id(), self.leader_id)
        self.assertEqual(dialog.tabs.count(), 8)

    @patch("moduly.audity.ui.audity_page.QMessageBox.question")
    def test_delete_selected_audit_removes_row(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = audit_service.create_audit(title="Ke smazání")
        page = self._create_page()
        page.status_filter.setCurrentText("Vše")
        page.refresh()
        self.assertEqual(page.table.rowCount(), 1)

        mock_question.return_value = QMessageBox.Yes
        page.table.selectRow(0)
        page.delete_selected_audit()

        self.assertEqual(page.table.rowCount(), 0)
        self.assertIsNone(audit_service.get_by_id(audit.id))

    def test_source_navigator_opens_audit(self) -> None:
        audit = audit_service.create_audit(title="Navigace")
        page = self._create_page()

        host = MagicMock()
        host._page_widgets = {"audity": page}
        host._show = MagicMock()
        source_navigator.configure(host)

        self.assertTrue(source_navigator.can_open(ENTITY_AUDITY, audit.id))

        with patch("moduly.audity.ui.audity_page.exec_maximized", return_value=False):
            opened = source_navigator.open(ENTITY_AUDITY, audit.id)

        self.assertTrue(opened)
        host._show.assert_called_once_with("audity")


if __name__ == "__main__":
    unittest.main()
