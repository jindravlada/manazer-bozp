import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QSplitter

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import (
        AUDIT_PROGRAM_PLANNED_VISITS_COLUMN_TERM,
        AUDIT_PROGRAM_STATUS_DRAFT,
        AUDIT_PROGRAM_STATUS_LABELS,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_program_visit_formatting import format_planned_term
    from moduly.audity.ui.audit_program_dashboard_widget import AuditProgramDashboardWidget
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.audity.ui.audit_program_planned_visits_widget import (
        AuditProgramPlannedVisitsWidget,
    )


class AuditProgramManagerErgonomicsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_dialog(self) -> AuditProgramManagerDialog:
        dialog = AuditProgramManagerDialog()
        dialog.showMaximized()
        QApplication.processEvents()
        return dialog

    def test_program_panels_use_module_panel_style(self) -> None:
        dialog = self._create_dialog()

        module_panels = [
            widget
            for widget in dialog.findChildren(QFrame)
            if widget.objectName() == "ModulePanel"
        ]
        self.assertGreaterEqual(len(module_panels), 4)

    def test_program_detail_is_compact_with_status_badge(self) -> None:
        program = audit_program_service.create_program(
            name="ZX-ZF 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )

        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        QApplication.processEvents()

        self.assertEqual(dialog._program_title_label.text(), "ZX-ZF 2026–2029")
        self.assertIn("2026", dialog._program_period_label.text())
        self.assertIn("2029", dialog._program_period_label.text())
        self.assertIn(
            AUDIT_PROGRAM_STATUS_LABELS[AUDIT_PROGRAM_STATUS_DRAFT],
            dialog._program_status_badge.text(),
        )
        self.assertEqual(
            dialog._program_status_badge.property("programStatus"),
            AUDIT_PROGRAM_STATUS_DRAFT,
        )

    def test_dashboard_summary_uses_two_columns(self) -> None:
        widget = AuditProgramDashboardWidget()
        widget.load_program(None)

        self.assertTrue(hasattr(widget, "_findings_summary_label"))
        self.assertTrue(hasattr(widget, "_tasks_summary_label"))
        self.assertIn("Celkem:", widget._findings_summary_label.text())
        self.assertIn("Celkem:", widget._tasks_summary_label.text())
        self.assertNotIn("Celkem zjištění", widget._findings_summary_label.text())

    def test_main_splitter_gives_more_space_to_dashboard(self) -> None:
        dialog = self._create_dialog()
        vertical_splitters = [
            splitter
            for splitter in dialog.findChildren(QSplitter)
            if splitter.orientation() == Qt.Orientation.Vertical
        ]
        self.assertTrue(vertical_splitters)
        main_splitter = vertical_splitters[0]
        sizes = main_splitter.sizes()
        self.assertEqual(len(sizes), 2)
        self.assertGreater(sizes[1], sizes[0])

    def test_planned_visits_term_column_shows_date_or_month(self) -> None:
        self.assertEqual(
            format_planned_term(
                planned_date=date(2026, 4, 15),
                planned_year=2026,
                planned_month=4,
            ),
            "15. 4. 2026",
        )
        self.assertEqual(
            format_planned_term(
                planned_date=None,
                planned_year=2026,
                planned_month=4,
            ),
            "Duben 2026",
        )

        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=10,
            workplace_name="Provoz A",
            audit_interval_months=6,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
            planned_date=date(2026, 4, 15),
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=10,
        )

        widget = AuditProgramPlannedVisitsWidget()
        widget.load_program(program.id)

        self.assertEqual(
            widget._table.horizontalHeaderItem(0).text(),
            AUDIT_PROGRAM_PLANNED_VISITS_COLUMN_TERM,
        )
        terms = {
            widget._table.item(row, 0).text()
            for row in range(widget._table.rowCount())
        }
        self.assertIn("15. 4. 2026", terms)
        self.assertIn("Říjen 2026", terms)


if __name__ == "__main__":
    unittest.main()
