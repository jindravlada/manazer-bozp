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
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AuditProgramSupplementWorkplacesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _create_program(self):
        return audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )

    def test_list_missing_auditable_workplaces(self) -> None:
        program = self._create_program()
        existing = settings_service.save_workplace(name="Existující", audit_enabled=True)
        missing = settings_service.save_workplace(name="Nové auditované", audit_enabled=True)

        audit_program_service.add_workplace(
            program.id,
            workplace_id=existing.id,
            workplace_name=existing.name,
            audit_interval_months=6,
        )

        listed = audit_program_service.list_missing_auditable_workplaces(program.id)
        listed_ids = {item.workplace_id for item in listed}

        self.assertIn(missing.id, listed_ids)
        self.assertNotIn(existing.id, listed_ids)

    def test_supplement_adds_workplace_without_changing_existing_plan(self) -> None:
        program = self._create_program()
        existing = settings_service.save_workplace(name="Původní", audit_enabled=True)
        new_workplace = settings_service.save_workplace(name="Nové", audit_enabled=True)
        audit_program_service.add_workplace(
            program.id,
            workplace_id=existing.id,
            workplace_name=existing.name,
            audit_interval_months=6,
        )
        first = audit_program_service.generate_visits(program.id)
        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        original = {
            (visit.workplace_id, visit.planned_year, visit.planned_month)
            for visit in overview.visits
            if visit.workplace_id == existing.id and visit.program_id == program.id
        }
        self.assertGreater(len(original), 0)
        self.assertEqual(len(first.created_visits), len(original))

        result = audit_program_service.supplement_workplaces(program.id, (new_workplace.id,))

        self.assertEqual(result.added_workplaces, 1)
        self.assertGreater(result.created_visits, 0)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        stored_original = {
            (visit.workplace_id, visit.planned_year, visit.planned_month)
            for visit in overview.visits
            if visit.workplace_id == existing.id and visit.program_id == program.id
        }
        self.assertEqual(stored_original, original)

    def test_supplement_works_when_program_manually_modified(self) -> None:
        program = self._create_program()
        existing = settings_service.save_workplace(name="Původní ruční", audit_enabled=True)
        new_workplace = settings_service.save_workplace(name="Nové ruční", audit_enabled=True)
        audit_program_service.add_workplace(
            program.id,
            workplace_id=existing.id,
            workplace_name=existing.name,
            audit_interval_months=6,
        )
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
        self.assertTrue(audit_program_service.get_program(program.id).manual_planning)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        original = {
            (visit.workplace_id, visit.planned_year, visit.planned_month)
            for visit in overview.visits
            if visit.workplace_id == existing.id
        }
        original_processes = {
            (item.visit_id, item.process_id)
            for item in overview.visit_processes
            if item.visit_id in {visit.id for visit in overview.visits if visit.workplace_id == existing.id}
        }

        result = audit_program_service.supplement_workplaces(program.id, (new_workplace.id,))

        self.assertEqual(result.added_workplaces, 1)
        self.assertGreater(result.created_visits, 0)
        self.assertGreater(result.assigned_processes, 0)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        stored_original = {
            (visit.workplace_id, visit.planned_year, visit.planned_month)
            for visit in overview.visits
            if visit.workplace_id == existing.id
        }
        self.assertEqual(stored_original, original)

        stored_original_processes = {
            (item.visit_id, item.process_id)
            for item in overview.visit_processes
            if item.visit_id in {visit.id for visit in overview.visits if visit.workplace_id == existing.id}
        }
        self.assertEqual(stored_original_processes, original_processes)

        new_visits = [
            visit
            for visit in overview.visits
            if visit.workplace_id == new_workplace.id
        ]
        self.assertGreater(len(new_visits), 0)
        new_visit_ids = {visit.id for visit in new_visits}
        new_processes = [
            item for item in overview.visit_processes if item.visit_id in new_visit_ids
        ]
        self.assertGreater(len(new_processes), 0)

    def test_supplement_is_idempotent_for_existing_workplaces(self) -> None:
        program = self._create_program()
        workplace = settings_service.save_workplace(name="Jedno", audit_enabled=True)
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=6,
        )
        audit_program_service.generate_visits(program.id)
        before = audit_program_service.get_program_overview(program.id)
        assert before is not None
        visit_count_before = len(before.visits)

        result = audit_program_service.supplement_workplaces(program.id, (workplace.id,))

        self.assertEqual(result.added_workplaces, 0)
        self.assertEqual(result.created_visits, 0)

        after = audit_program_service.get_program_overview(program.id)
        assert after is not None
        visits_before = {
            (visit.id, visit.planned_year, visit.planned_month)
            for visit in before.visits
            if visit.program_id == program.id
        }
        visits_after = {
            (visit.id, visit.planned_year, visit.planned_month)
            for visit in after.visits
            if visit.program_id == program.id
        }
        self.assertEqual(visits_after, visits_before)


if __name__ == "__main__":
    unittest.main()
