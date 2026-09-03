import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QHeaderView

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.table_utils import configure_table_columns
    from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_program_visit_formatting import (
        format_planned_processes_cell,
    )
    from moduly.audity.ui.audit_program_planned_visits_widget import (
        AuditProgramPlannedVisitsWidget,
        _COLUMN_AUDIT,
        _COLUMN_AUDIT_MIN_WIDTH,
    )
    from moduly.audity.ui.audit_table import AuditTable
    from tests.audit_v2a_test_support import prepare_v2_audit_create


class AuditTableErgonomicsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_audity_table_workplace_column_stretches(self) -> None:
        table = AuditTable()
        configure_table_columns(table, "audity")
        header = table.horizontalHeader()

        self.assertEqual(
            header.sectionResizeMode(4),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Interactive,
                msg=f"column {column}",
            )

    def test_compact_columns_keep_reasonable_widths(self) -> None:
        table = AuditTable()
        configure_table_columns(table, "audity")

        self.assertLessEqual(table.columnWidth(1), 100)
        self.assertLessEqual(table.columnWidth(2), 60)
        self.assertLessEqual(table.columnWidth(3), 120)


class PlannedProcessesFormattingTestCase(unittest.TestCase):
    def test_empty_processes(self) -> None:
        text, tooltip = format_planned_processes_cell(())
        self.assertEqual(text, "—")
        self.assertEqual(tooltip, "")

    def test_single_process(self) -> None:
        text, tooltip = format_planned_processes_cell(("Lidský faktor",))
        self.assertEqual(text, "1 proces: Lidský faktor")
        self.assertEqual(tooltip, "Lidský faktor")

    def test_multiple_processes_short_preview(self) -> None:
        text, tooltip = format_planned_processes_cell(
            ("Lidský faktor", "Monitoring", "Řízení rizik")
        )
        self.assertEqual(
            text,
            "3 procesy: Lidský faktor, Monitoring, Řízení rizik",
        )
        self.assertEqual(
            tooltip,
            "Lidský faktor\nMonitoring\nŘízení rizik",
        )

    def test_many_processes_use_ellipsis(self) -> None:
        names = (
            "Lidský faktor",
            "Monitoring",
            "Řízení rizik",
            "Dokumentace",
            "Školení",
        )
        text, tooltip = format_planned_processes_cell(names)
        self.assertEqual(
            text,
            "5 procesů: Lidský faktor, Monitoring, Řízení rizik...",
        )
        self.assertEqual(tooltip, "\n".join(names))


class PlannedVisitsTableErgonomicsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create(operation_name="Provoz A")
        self._system_wp, self._operation_wp = self._v2.__enter__()

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _create_program_with_processes(self, process_names: tuple[str, ...]):
        program = audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=4,
            planned_date=date(2026, 4, 15),
        )
        for index, name in enumerate(process_names):
            audit_program_service.add_visit_process(
                visit.id,
                process_id=f"process_{index}",
                process_name=name,
            )
        return program

    def test_planned_visits_column_resize_modes(self) -> None:
        widget = AuditProgramPlannedVisitsWidget()
        header = widget._table.horizontalHeader()

        self.assertEqual(
            header.sectionResizeMode(0),
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.assertEqual(
            header.sectionResizeMode(1),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(2),
            QHeaderView.ResizeMode.Interactive,
        )
        self.assertEqual(
            header.sectionResizeMode(3),
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.assertEqual(
            header.sectionResizeMode(4),
            QHeaderView.ResizeMode.Interactive,
        )

    def test_audit_column_fits_short_audit_number(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=10,
        )
        audit_program_service.create_audit_from_visit(visit.id, started_at=date(2026, 4, 10))

        widget = AuditProgramPlannedVisitsWidget()
        widget.load_program(program.id)

        self.assertGreaterEqual(
            widget._table.columnWidth(_COLUMN_AUDIT),
            _COLUMN_AUDIT_MIN_WIDTH,
        )
        item = widget._table.item(0, _COLUMN_AUDIT)
        assert item is not None
        self.assertNotEqual(item.text(), "—")
        self.assertIn("/2026", item.text())
        item.setText("10/2026")
        self.assertEqual(item.text(), "10/2026")

    def test_planned_processes_cell_has_short_text_and_tooltip(self) -> None:
        program = self._create_program_with_processes(
            (
                "Lidský faktor",
                "Monitoring",
                "Řízení rizik",
                "Dokumentace",
                "Školení",
            )
        )

        widget = AuditProgramPlannedVisitsWidget()
        widget.load_program(program.id)

        item = widget._table.item(0, 2)
        assert item is not None
        self.assertTrue(item.text().startswith("5 procesů:"))
        self.assertTrue(item.text().endswith("..."))
        self.assertNotIn(", ".join(
            (
                "Lidský faktor",
                "Monitoring",
                "Řízení rizik",
                "Dokumentace",
                "Školení",
            )
        ), item.text())
        self.assertIn("Dokumentace", item.toolTip())
        self.assertIn("Školení", item.toolTip())
        self.assertEqual(
            sorted(item.toolTip().splitlines()),
            sorted(
                [
                    "Lidský faktor",
                    "Monitoring",
                    "Řízení rizik",
                    "Dokumentace",
                    "Školení",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
