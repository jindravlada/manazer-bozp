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
        AUDIT_PROGRAM_STATUS_DRAFT,
        AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED,
        AUDIT_PROGRAM_VISIT_STATUS_PLANNED,
        AUDIT_STANDARD_ISO_45001,
        AUDIT_STANDARD_ISO_9001,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.nastaveni.constants.workplace_audit_constants import (
        DEFAULT_PREFERRED_AUDIT_MONTHS,
    )
    from moduly.nastaveni.sluzby.workplace_audit_planning import plan_visit_months


class AuditProgramServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _create_program(self):
        program = audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
            description="Testovací program auditů",
        )
        return program

    def test_create_program(self) -> None:
        program = self._create_program()

        self.assertEqual(program.name, "Interní audity 2026–2029")
        self.assertEqual(program.status, AUDIT_PROGRAM_STATUS_DRAFT)
        self.assertTrue(program.number.startswith("PA-"))
        self.assertEqual(
            audit_program_service.parse_standards(program.standards_json),
            [AUDIT_STANDARD_ISO_45001, AUDIT_STANDARD_ISO_9001],
        )

    def test_list_programs(self) -> None:
        before = len(audit_program_service.list_programs())
        self._create_program()

        self.assertEqual(len(audit_program_service.list_programs()), before + 1)

    def test_add_workplace(self) -> None:
        program = self._create_program()

        workplace = audit_program_service.add_workplace(
            program.id,
            workplace_id=10,
            workplace_name="Provoz Gamma",
            audit_interval_months=12,
        )

        self.assertEqual(workplace.program_id, program.id)
        self.assertEqual(workplace.workplace_name, "Provoz Gamma")
        self.assertEqual(workplace.audit_interval_months, 12)
        self.assertTrue(workplace.active)

    def test_add_visit(self) -> None:
        program = self._create_program()

        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
            planned_date=date(2026, 4, 15),
        )

        self.assertEqual(visit.program_id, program.id)
        self.assertEqual(visit.planned_year, 2026)
        self.assertEqual(visit.planned_month, 4)
        self.assertEqual(visit.status, AUDIT_PROGRAM_VISIT_STATUS_PLANNED)

    def test_add_visit_process(self) -> None:
        program = self._create_program()
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
        )

        visit_process = audit_program_service.add_visit_process(
            visit.id,
            process_id="urazy_mimo_udalosti",
            process_name="Úrazy mimo pracovní úraz",
            standards=[AUDIT_STANDARD_ISO_45001],
        )

        self.assertEqual(visit_process.visit_id, visit.id)
        self.assertEqual(visit_process.process_id, "urazy_mimo_udalosti")
        self.assertEqual(visit_process.status, AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED)

    def test_get_program_overview(self) -> None:
        program = self._create_program()
        audit_program_service.add_workplace(
            program.id,
            workplace_id=10,
            workplace_name="Provoz Gamma",
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=4,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="urazy_mimo_udalosti",
            process_name="Úrazy mimo pracovní úraz",
        )

        overview = audit_program_service.get_program_overview(program.id)

        assert overview is not None
        self.assertEqual(overview.program.id, program.id)
        self.assertEqual(len(overview.workplaces), 1)
        self.assertEqual(len(overview.visits), 1)
        self.assertEqual(len(overview.visit_processes), 1)

    def test_visit_to_process_relation(self) -> None:
        program = self._create_program()
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=20,
            planned_year=2027,
            planned_month=10,
        )
        first = audit_program_service.add_visit_process(
            visit.id,
            process_id="rizeni_zmen",
            process_name="Řízení změn",
        )
        second = audit_program_service.add_visit_process(
            visit.id,
            process_id="prezkoumani_vedenim",
            process_name="Přezkoumání vedením",
        )

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None

        visit_processes = [
            item for item in overview.visit_processes if item.visit_id == visit.id
        ]
        self.assertEqual(len(visit_processes), 2)
        self.assertEqual({item.id for item in visit_processes}, {first.id, second.id})

    def test_get_program_returns_none_for_missing(self) -> None:
        self.assertIsNone(audit_program_service.get_program(999_999))


class AuditProgramGenerationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

        import core.services.editable_catalog_service as editable_catalog_module

        importlib.reload(editable_catalog_module)
        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

        audit_knowledge_service.ensure_catalogs()
        cls._active_process_count = len(audit_knowledge_service.get_processes())

    def _create_program_with_workplace(
        self,
        *,
        workplace_id: int | None = None,
        interval: int = 6,
        active: bool = True,
        name: str = "Provoz Gamma",
    ):
        from moduly.nastaveni.sluzby.settings_service import settings_service

        if workplace_id is None:
            workplace_id = settings_service.save_workplace(
                name=name,
                address="",
                note="",
                active=True,
                audit_enabled=True,
                audit_interval_months=interval,
            ).id
        program = audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace_id,
            workplace_name=name,
            audit_interval_months=interval,
            active=active,
        )
        return program, workplace_id

    def test_generate_visits_six_month_cycle(self) -> None:
        program, workplace_id = self._create_program_with_workplace(interval=6)
        expected = plan_visit_months(
            date(2026, 4, 1),
            date(2029, 3, 31),
            6,
            DEFAULT_PREFERRED_AUDIT_MONTHS,
            month_usage={},
            workplace_key=workplace_id,
        )

        result = audit_program_service.generate_visits(program.id)

        self.assertEqual(len(result.created_visits), 6)
        self.assertEqual(
            [(visit.planned_year, visit.planned_month) for visit in result.created_visits],
            expected,
        )

    def test_generate_visits_is_idempotent(self) -> None:
        program, _workplace_id = self._create_program_with_workplace(interval=6)

        first = audit_program_service.generate_visits(program.id)
        second = audit_program_service.generate_visits(program.id)

        self.assertEqual(len(first.created_visits), 6)
        self.assertEqual(len(second.created_visits), 0)
        self.assertEqual(second.skipped_existing, 6)
        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        self.assertEqual(len(overview.visits), 6)

    def test_generate_visits_ignores_inactive_workplace(self) -> None:
        program, active_workplace_id = self._create_program_with_workplace(interval=6)
        audit_program_service.add_workplace(
            program.id,
            workplace_id=20,
            workplace_name="Neaktivní sklad",
            audit_interval_months=6,
            active=False,
        )

        result = audit_program_service.generate_visits(program.id)

        self.assertEqual(len(result.created_visits), 6)
        workplace_ids = {visit.workplace_id for visit in result.created_visits}
        self.assertEqual(workplace_ids, {active_workplace_id})

    def test_distribute_processes_covers_all_active_processes(self) -> None:
        program, _workplace_id = self._create_program_with_workplace(interval=6)
        audit_program_service.generate_visits(program.id)

        distribution = audit_program_service.distribute_processes(program.id)
        coverage = audit_program_service.get_program_coverage(program.id)

        assert coverage is not None
        self.assertEqual(len(distribution.created_processes), self._active_process_count)
        self.assertEqual(coverage.planned_process_count, self._active_process_count)
        self.assertEqual(coverage.missing_by_workplace[0].missing_process_ids, ())

    def test_distribute_processes_is_idempotent(self) -> None:
        program, _workplace_id = self._create_program_with_workplace(interval=6)
        audit_program_service.generate_visits(program.id)

        first = audit_program_service.distribute_processes(program.id)
        second = audit_program_service.distribute_processes(program.id)

        self.assertGreater(len(first.created_processes), 0)
        self.assertEqual(len(second.created_processes), 0)
        self.assertEqual(second.skipped_existing, len(first.created_processes))

    def test_distribute_processes_does_not_overwrite_manual_plan(self) -> None:
        program, _workplace_id = self._create_program_with_workplace(interval=6)
        audit_program_service.generate_visits(program.id)
        audit_program_service.distribute_processes(program.id)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        visit = overview.visits[0]
        manual = audit_program_service.add_visit_process(
            visit.id,
            process_id="manual_only_process",
            process_name="Ručně plánovaný proces",
            note="manual-plan",
        )

        second = audit_program_service.distribute_processes(program.id)
        refreshed = audit_program_service.get_program_overview(program.id)
        assert refreshed is not None

        stored_manual = next(
            item for item in refreshed.visit_processes if item.id == manual.id
        )
        self.assertEqual(stored_manual.note, "manual-plan")
        self.assertEqual(len(second.created_processes), 0)

    def test_get_program_coverage_counts(self) -> None:
        program, _workplace_id = self._create_program_with_workplace(interval=6)
        audit_program_service.generate_visits(program.id)
        audit_program_service.distribute_processes(program.id)

        coverage = audit_program_service.get_program_coverage(program.id)

        assert coverage is not None
        self.assertEqual(coverage.workplace_count, 1)
        self.assertEqual(coverage.visit_count, 6)
        self.assertEqual(coverage.planned_process_count, self._active_process_count)
        self.assertEqual(coverage.completed_process_count, 0)
        self.assertEqual(coverage.completion_percent, 0.0)


if __name__ == "__main__":
    unittest.main()
