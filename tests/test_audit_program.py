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


if __name__ == "__main__":
    unittest.main()
