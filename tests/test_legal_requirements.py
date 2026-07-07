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

    from core.shared.constants import ENTITY_LEGAL_REQUIREMENT
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_CASTECNE_SPLNENO,
        COMPLIANCE_NESPLNENO,
        COMPLIANCE_SPLNENO,
        PERIODICITY_ROCNE,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_export_context_service import (
        legal_requirement_export_context_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        calculate_next_verification_date,
        legal_requirement_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_task_service import (
        legal_requirement_task_service,
    )
    from moduly.ukoly.sluzby.task_service import task_service


class LegalRequirementServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for requirement in legal_requirement_service.get_all():
            requirement.active = False
            legal_requirement_service.repository.update(requirement)

    def _create_requirement(self, **kwargs):
        defaults = {
            "regulation_name": "Zákoník práce",
            "regulation_number": "262/2006 Sb.",
            "provision": "§ 101",
            "area": "BOZP",
            "requirement_summary": "Zajistit bezpečnost práce",
            "organization_impact": "Nutné školení zaměstnanců",
            "verification_periodicity": PERIODICITY_ROCNE,
            "compliance_status": COMPLIANCE_SPLNENO,
        }
        defaults.update(kwargs)
        return legal_requirement_service.create_requirement(**defaults)

    def test_create_requirement(self) -> None:
        requirement = self._create_requirement()

        self.assertIsNotNone(requirement.id)
        self.assertEqual(requirement.regulation_name, "Zákoník práce")
        self.assertEqual(requirement.area, "BOZP")
        self.assertTrue(requirement.active)

    def test_update_requirement(self) -> None:
        requirement = self._create_requirement()
        updated = legal_requirement_service.update_requirement(
            requirement.id,
            regulation_name="Nařízení vlády",
            regulation_number="378/2001 Sb.",
            provision="§ 4",
            area="OOPP",
            requirement_summary="Poskytnout OOPP",
            organization_impact="Nákup OOPP",
            responsible_person_id=None,
            verification_periodicity=PERIODICITY_ROCNE,
            last_verification_date=None,
            next_verification_date=None,
            compliance_status=COMPLIANCE_NESPLNENO,
            note="Nutné doplnit",
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.regulation_name, "Nařízení vlády")
        self.assertEqual(updated.compliance_status, COMPLIANCE_NESPLNENO)
        self.assertEqual(updated.note, "Nutné doplnit")

    def test_archive_requirement(self) -> None:
        requirement = self._create_requirement()
        archived = legal_requirement_service.archive_requirement(requirement.id)

        assert archived is not None
        self.assertFalse(archived.active)

        restored = legal_requirement_service.restore_requirement(requirement.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_record_verification_updates_requirement(self) -> None:
        requirement = self._create_requirement(
            compliance_status=COMPLIANCE_SPLNENO,
            verification_periodicity=PERIODICITY_ROCNE,
        )
        check_date = date(2026, 1, 15)

        updated = legal_requirement_service.record_verification(
            requirement.id,
            check_date=check_date,
            result=COMPLIANCE_NESPLNENO,
            comment="Chybí dokumentace",
            next_check_date=date(2026, 7, 1),
        )

        assert updated is not None
        self.assertEqual(updated.last_verification_date, check_date)
        self.assertEqual(updated.compliance_status, COMPLIANCE_NESPLNENO)
        self.assertEqual(updated.next_verification_date, date(2026, 7, 1))

        checks = legal_requirement_service.get_checks(requirement.id)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].result, COMPLIANCE_NESPLNENO)
        self.assertEqual(checks[0].comment, "Chybí dokumentace")

    def test_calculate_next_verification_date(self) -> None:
        check_date = date(2026, 3, 31)
        next_date = calculate_next_verification_date(check_date, PERIODICITY_ROCNE)
        self.assertEqual(next_date, date(2027, 3, 31))

        explicit = calculate_next_verification_date(
            check_date,
            PERIODICITY_ROCNE,
            explicit_next_date=date(2026, 12, 31),
        )
        self.assertEqual(explicit, date(2026, 12, 31))

    def test_create_task_from_requirement_links_source(self) -> None:
        requirement = self._create_requirement(compliance_status=COMPLIANCE_NESPLNENO)

        task = legal_requirement_task_service.create_task_from_requirement(requirement.id)

        self.assertEqual(task.source_module, ENTITY_LEGAL_REQUIREMENT)
        self.assertEqual(task.source_record_id, requirement.id)
        self.assertIn("Zákoník práce", task.description)

        existing = legal_requirement_task_service.create_task_from_requirement(requirement.id)
        self.assertEqual(existing.id, task.id)

    def test_create_task_only_for_non_compliance(self) -> None:
        requirement = self._create_requirement(compliance_status=COMPLIANCE_SPLNENO)
        self.assertFalse(legal_requirement_task_service.can_create_task(requirement))

        partial = self._create_requirement(compliance_status=COMPLIANCE_CASTECNE_SPLNENO)
        self.assertTrue(legal_requirement_task_service.can_create_task(partial))

    def test_export_context_builds_rows(self) -> None:
        requirement = self._create_requirement()
        context = legal_requirement_export_context_service.build(active_only=None)

        self.assertGreaterEqual(context.total_count, 1)
        row = next(item for item in context.rows if item.requirement_id == requirement.id)
        self.assertEqual(row.regulation_name, "Zákoník práce")
        self.assertEqual(row.area, "BOZP")


if __name__ == "__main__":
    unittest.main()
