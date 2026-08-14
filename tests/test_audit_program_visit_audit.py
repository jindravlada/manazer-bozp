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

    from moduly.audity.constants import (
        AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
        AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED,
        AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
        AUDIT_PROGRAM_VISIT_STATUS_PLANNED,
        AUDIT_STATUS_DOKONCENO,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from tests.audit_v2a_test_support import prepare_v2_audit_create


class AuditProgramVisitAuditTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create()
        self._system_wp, self._operation_wp = self._v2.__enter__()

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _create_program_with_visit(self):
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
        audit_program_service.add_visit_process(
            visit.id,
            process_id="dokumentace",
            process_name="Dokumentace",
            standards=["ISO 45001"],
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="rizeni_rizik",
            process_name="Řízení rizik",
            standards=["ISO 45001"],
        )
        return program, visit

    def test_create_audit_from_visit_prefills_and_links(self) -> None:
        program, visit = self._create_program_with_visit()

        audit = audit_program_service.create_audit_from_visit(visit.id)

        self.assertEqual(audit.program_id, program.id)
        self.assertEqual(audit.program_visit_id, visit.id)
        self.assertEqual(audit.workplace_id, self._operation_wp.id)
        self.assertEqual(audit.planned_month, 4)
        self.assertEqual(audit.year, 2026)
        self.assertEqual(audit.audit_date, date(2026, 4, 15))
        self.assertTrue(audit.title)

        refreshed_visit = audit_program_service.repository.get_visit(visit.id)
        assert refreshed_visit is not None
        self.assertEqual(refreshed_visit.audit_id, audit.id)
        self.assertEqual(refreshed_visit.status, AUDIT_PROGRAM_VISIT_STATUS_PLANNED)

    def test_create_audit_from_visit_blocks_duplicate(self) -> None:
        _, visit = self._create_program_with_visit()
        audit_program_service.create_audit_from_visit(visit.id)

        with self.assertRaises(ValueError):
            audit_program_service.create_audit_from_visit(visit.id)

    def test_get_visit_audit_context(self) -> None:
        _, visit = self._create_program_with_visit()

        context = audit_program_service.get_visit_audit_context(visit.id)

        assert context is not None
        self.assertEqual(context.visit_id, visit.id)
        self.assertEqual(context.planned_process_ids, ("dokumentace", "rizeni_rizik"))
        self.assertIn("ISO 45001", context.standards)

    def test_sync_on_audit_completed_updates_visit_and_processes(self) -> None:
        _, visit = self._create_program_with_visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)
        finished_at = date(2026, 4, 20)

        audit_program_service.sync_on_audit_completed(audit.id, finished_at=finished_at)

        refreshed_visit = audit_program_service.repository.get_visit(visit.id)
        assert refreshed_visit is not None
        self.assertEqual(refreshed_visit.status, AUDIT_PROGRAM_VISIT_STATUS_COMPLETED)

        processes = audit_program_service.repository.list_visit_processes(visit.id)
        self.assertEqual(len(processes), 2)
        for visit_process in processes:
            self.assertEqual(visit_process.status, AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED)
            self.assertEqual(visit_process.audit_id, audit.id)
            self.assertIsNotNone(visit_process.completed_at)

    def test_update_audit_completion_triggers_program_sync(self) -> None:
        _, visit = self._create_program_with_visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)
        finished_at = date(2026, 4, 22)

        updated = audit_service.update_audit(
            audit.id,
            finished_at=finished_at,
            conclusion_text="Závěr programu návštěvy.",
        )

        assert updated is not None
        self.assertEqual(updated.status, AUDIT_STATUS_DOKONCENO)

        refreshed_visit = audit_program_service.get_visit_by_audit_id(audit.id)
        assert refreshed_visit is not None
        self.assertEqual(refreshed_visit.status, AUDIT_PROGRAM_VISIT_STATUS_COMPLETED)

        processes = audit_program_service.repository.list_visit_processes(visit.id)
        self.assertTrue(processes)
        self.assertTrue(
            all(
                item.status == AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED
                for item in processes
            )
        )

    def test_coverage_counts_completed_visits_and_processes(self) -> None:
        program, visit = self._create_program_with_visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)
        audit_service.update_audit(
            audit.id,
            finished_at=date(2026, 4, 22),
            conclusion_text="Závěr coverage.",
        )

        coverage = audit_program_service.get_program_coverage(program.id)

        assert coverage is not None
        self.assertEqual(coverage.completed_visit_count, 1)
        self.assertEqual(coverage.completed_process_count, 2)
        self.assertEqual(coverage.completion_percent, 100.0)

    def test_get_visit_by_audit_id(self) -> None:
        _, visit = self._create_program_with_visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)

        linked = audit_program_service.get_visit_by_audit_id(audit.id)

        assert linked is not None
        self.assertEqual(linked.id, visit.id)


if __name__ == "__main__":
    unittest.main()
