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

    import core.services.editable_catalog_service as editable_catalog_module

    importlib.reload(editable_catalog_module)

    from moduly.audity.constants import (
        AUDIT_PROGRAM_MANUAL_DISTRIBUTE_BLOCKED,
        AUDIT_PROGRAM_MANUAL_GENERATE_BLOCKED,
        AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.ui.audit_program_plan_tree_widget import (
        NODE_PROCESS,
        NODE_VISIT,
        NODE_WORKPLACE,
        AuditProgramPlanTreeWidget,
    )


class AuditProgramPlanningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def _create_program_with_workplace(self, *, interval: int = 6):
        program = audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=10,
            workplace_name="Provoz Gamma",
            audit_interval_months=interval,
        )
        return program

    def test_create_manual_visit_marks_manual_planning(self) -> None:
        program = self._create_program_with_workplace()

        visit = audit_program_service.create_manual_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=5,
            note="Ruční návštěva",
        )

        refreshed = audit_program_service.get_program(program.id)
        assert refreshed is not None
        self.assertTrue(refreshed.manual_planning)
        self.assertEqual(visit.planned_month, 5)
        self.assertEqual(visit.note, "Ruční návštěva")

    def test_update_visit_plan_changes_month_and_order(self) -> None:
        program = self._create_program_with_workplace()
        first = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
        )
        second = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=10,
        )

        audit_program_service.update_visit_plan(
            second.id,
            planned_year=2026,
            planned_month=5,
        )

        ordered = audit_program_service.list_workplace_visits(program.id, 10)
        self.assertEqual([visit.id for visit in ordered], [first.id, second.id])
        self.assertEqual(ordered[1].planned_month, 5)
        self.assertTrue(audit_program_service.get_program(program.id).manual_planning)

    def test_move_visit_process_between_visits(self) -> None:
        program = self._create_program_with_workplace()
        source_visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
        )
        target_visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=10,
        )
        visit_process = audit_program_service.add_visit_process(
            source_visit.id,
            process_id="rizeni_rizik",
            process_name="Řízení rizik",
        )

        moved = audit_program_service.move_visit_process(visit_process.id, target_visit.id)

        self.assertEqual(moved.visit_id, target_visit.id)
        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        source_processes = [
            item for item in overview.visit_processes if item.visit_id == source_visit.id
        ]
        target_processes = [
            item for item in overview.visit_processes if item.visit_id == target_visit.id
        ]
        self.assertEqual(source_processes, [])
        self.assertEqual(len(target_processes), 1)
        self.assertTrue(audit_program_service.get_program(program.id).manual_planning)

    def test_manual_changes_block_generate_and_distribute(self) -> None:
        program = self._create_program_with_workplace()
        audit_program_service.generate_visits(program.id)
        audit_program_service.distribute_processes(program.id)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        audit_program_service.update_visit_plan(
            overview.visits[0].id,
            planned_year=overview.visits[0].planned_year,
            planned_month=(overview.visits[0].planned_month or 4) + 1
            if (overview.visits[0].planned_month or 4) < 12
            else 1,
        )

        with self.assertRaisesRegex(ValueError, AUDIT_PROGRAM_MANUAL_GENERATE_BLOCKED):
            audit_program_service.generate_visits(program.id)
        with self.assertRaisesRegex(ValueError, AUDIT_PROGRAM_MANUAL_DISTRIBUTE_BLOCKED):
            audit_program_service.distribute_processes(program.id)

    def test_skip_visit_excludes_from_coverage(self) -> None:
        program = self._create_program_with_workplace()
        audit_program_service.generate_visits(program.id)
        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None

        before = audit_program_service.get_program_coverage(program.id)
        assert before is not None
        self.assertEqual(before.visit_count, len(overview.visits))

        audit_program_service.skip_visit(overview.visits[0].id)

        after = audit_program_service.get_program_coverage(program.id)
        assert after is not None
        self.assertEqual(after.visit_count, before.visit_count - 1)
        skipped = audit_program_service.repository.get_visit(overview.visits[0].id)
        assert skipped is not None
        self.assertEqual(skipped.status, AUDIT_PROGRAM_VISIT_STATUS_SKIPPED)

    def test_plan_tree_populates_hierarchy(self) -> None:
        program = self._create_program_with_workplace()
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="dokumentace",
            process_name="Dokumentace",
        )
        skipped_visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=10,
        )
        audit_program_service.skip_visit(skipped_visit.id)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None

        tree = AuditProgramPlanTreeWidget()
        tree.populate(overview)

        self.assertEqual(tree.topLevelItemCount(), 1)
        workplace_item = tree.topLevelItem(0)
        self.assertEqual(AuditProgramPlanTreeWidget.node_type(workplace_item), NODE_WORKPLACE)
        self.assertEqual(workplace_item.childCount(), 2)

        active_visit_item = workplace_item.child(0)
        self.assertEqual(AuditProgramPlanTreeWidget.node_type(active_visit_item), NODE_VISIT)
        self.assertIn("Duben 2026", active_visit_item.text(0))
        self.assertEqual(active_visit_item.childCount(), 1)
        process_item = active_visit_item.child(0)
        self.assertEqual(AuditProgramPlanTreeWidget.node_type(process_item), NODE_PROCESS)
        self.assertIn("Dokumentace", process_item.text(0))

        skipped_visit_item = workplace_item.child(1)
        self.assertIn("(Zrušeno)", skipped_visit_item.text(0))
        self.assertTrue(skipped_visit_item.font(0).strikeOut())


if __name__ == "__main__":
    unittest.main()
