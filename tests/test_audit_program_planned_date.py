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

    from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_program_visit_formatting import (
        format_visit_period_label,
        visit_tree_label,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_program_planned_visits_widget import (
        AuditProgramPlannedVisitsWidget,
    )
    from moduly.audity.ui.audit_program_plan_tree_widget import AuditProgramPlanTreeWidget


class AuditProgramPlannedDateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _create_program_with_visit(self, *, planned_date: date | None = date(2026, 4, 15)):
        program = audit_program_service.create_program(
            name="Interní audity 2026–2029",
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
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
            planned_date=planned_date,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="rizeni_rizik",
            process_name="Řízení rizik",
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="dokumentace",
            process_name="Řízení dokumentace",
        )
        return program, visit

    def test_planned_date_can_be_saved_on_visit(self) -> None:
        program, visit = self._create_program_with_visit()

        updated = audit_program_service.update_visit_plan(
            visit.id,
            planned_year=2026,
            planned_month=4,
            planned_date=date(2026, 4, 20),
        )

        self.assertEqual(updated.planned_date, date(2026, 4, 20))
        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        self.assertEqual(overview.visits[0].planned_date, date(2026, 4, 20))

    def test_planned_date_visible_in_program_tree(self) -> None:
        program, visit = self._create_program_with_visit()

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None

        self.assertEqual(
            format_visit_period_label(visit),
            "15. 4. 2026 — Duben 2026",
        )

        tree = AuditProgramPlanTreeWidget()
        tree.populate(overview)
        visit_item = tree.topLevelItem(0).child(0)
        self.assertIn("15. 4. 2026", visit_item.text(0))
        self.assertIn("Duben 2026", visit_item.text(0))

    def test_visit_without_planned_date_shows_month_only(self) -> None:
        program, visit = self._create_program_with_visit(planned_date=None)

        self.assertEqual(format_visit_period_label(visit), "Duben 2026")
        self.assertEqual(visit_tree_label(visit), "Duben 2026")

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        tree = AuditProgramPlanTreeWidget()
        tree.populate(overview)
        self.assertEqual(tree.topLevelItem(0).child(0).text(0), "Duben 2026")

    def test_start_audit_copies_planned_date_to_audit_spis(self) -> None:
        _, visit = self._create_program_with_visit()

        audit = audit_program_service.create_audit_from_visit(visit.id)

        self.assertEqual(audit.audit_date, date(2026, 4, 15))

    def test_start_audit_without_planned_date_keeps_current_behavior(self) -> None:
        _, visit = self._create_program_with_visit(planned_date=None)

        audit = audit_program_service.create_audit_from_visit(visit.id)

        self.assertIsNone(audit.audit_date)
        self.assertEqual(audit.planned_month, 4)
        self.assertEqual(audit.year, 2026)

    def test_planned_visits_overview_shows_details(self) -> None:
        program, visit = self._create_program_with_visit()

        rows = audit_program_service.get_planned_visits_overview(program.id)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.visit_id, visit.id)
        self.assertEqual(row.planned_date, date(2026, 4, 15))
        self.assertEqual(row.workplace_name, "Provoz A")
        self.assertEqual(row.process_names, ("Řízení dokumentace", "Řízení rizik"))
        self.assertEqual(row.status, "planned")
        self.assertIsNone(row.audit_number)

    def test_planned_visits_widget_displays_table(self) -> None:
        program, _visit = self._create_program_with_visit()

        widget = AuditProgramPlannedVisitsWidget()
        widget.load_program(program.id)

        self.assertEqual(widget._table.rowCount(), 1)
        self.assertEqual(widget._table.columnCount(), 5)
        self.assertEqual(widget._table.horizontalHeaderItem(0).text(), "Termín")
        self.assertEqual(widget._table.item(0, 0).text(), "15. 4. 2026")
        self.assertEqual(widget._table.item(0, 1).text(), "Provoz A")
        self.assertIn("Řízení rizik", widget._table.item(0, 2).text())
        self.assertEqual(widget._table.item(0, 3).text(), "Plánováno")
        self.assertEqual(widget._table.item(0, 4).text(), "—")

    def test_main_audit_list_excludes_unstarted_program_visits(self) -> None:
        program, visit = self._create_program_with_visit()
        before_count = len(audit_service.get_all())

        audit_program_service.generate_visits(program.id)
        after_generate_count = len(audit_service.get_all())
        self.assertEqual(after_generate_count, before_count)

        audit = audit_program_service.create_audit_from_visit(visit.id)
        after_start_count = len(audit_service.get_all())
        self.assertEqual(after_start_count, before_count + 1)
        self.assertEqual(audit.program_visit_id, visit.id)


if __name__ == "__main__":
    unittest.main()
