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
    from moduly.pravni_pozadavky.sluzby.legal_requirement_sanction_service import (
        legal_requirement_sanction_service,
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
        self.assertEqual(row.sanctions, [])
        self.assertEqual(row.links, [])

    def test_export_context_includes_links(self) -> None:
        from core.shared.constants import ENTITY_RISK, LINK_LEGAL_BASIS
        from core.shared.sluzby.entity_link_service import entity_link_service

        requirement = self._create_requirement()
        entity_link_service.create(
            source_type=ENTITY_LEGAL_REQUIREMENT,
            source_id=requirement.id,
            target_type=ENTITY_RISK,
            target_id=15,
            link_type=LINK_LEGAL_BASIS,
            note="Právní základ rizika",
        )

        context = legal_requirement_export_context_service.build_for_requirement(requirement.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(len(row.links), 1)
        self.assertEqual(row.links[0].target_type, ENTITY_RISK)
        self.assertEqual(row.links[0].target_id, 15)
        self.assertEqual(row.links[0].link_type, LINK_LEGAL_BASIS)
        self.assertEqual(row.links[0].note, "Právní základ rizika")

    def test_create_sanction_for_requirement(self) -> None:
        requirement = self._create_requirement()
        sanction = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            authority="OIP",
            legal_reference="§ 5 odst. 1",
            description="Pokuta za porušení povinnosti",
            max_amount="50000",
            currency="Kč",
            note="Test",
        )

        self.assertIsNotNone(sanction.id)
        self.assertEqual(sanction.requirement_id, requirement.id)
        self.assertEqual(sanction.currency, "Kč")

    def test_update_sanction(self) -> None:
        requirement = self._create_requirement()
        sanction = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            description="Původní popis",
        )
        updated = legal_requirement_sanction_service.update(
            sanction.id,
            authority="KHS",
            legal_reference="§ 10",
            description="Upravený popis",
            max_amount=None,
            currency="Kč",
            note="Poznámka",
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.authority, "KHS")
        self.assertEqual(updated.description, "Upravený popis")
        self.assertIsNone(updated.max_amount)

    def test_deactivate_and_restore_sanction(self) -> None:
        requirement = self._create_requirement()
        sanction = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            description="Sankce k deaktivaci",
        )

        deactivated = legal_requirement_sanction_service.deactivate(sanction.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_requirement_sanction_service.list_by_requirement(requirement.id)
        self.assertEqual(active_only, [])

        restored = legal_requirement_sanction_service.restore(sanction.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_requirement_can_have_multiple_sanctions(self) -> None:
        requirement = self._create_requirement()
        first = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            description="První sankce",
        )
        second = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            description="Druhá sankce",
        )

        sanctions = legal_requirement_sanction_service.list_by_requirement(requirement.id)
        self.assertEqual(len(sanctions), 2)
        self.assertEqual({item.id for item in sanctions}, {first.id, second.id})

    def test_archive_requirement_keeps_sanctions(self) -> None:
        requirement = self._create_requirement()
        sanction = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            description="Sankce přežije archivaci",
        )

        archived = legal_requirement_service.archive_requirement(requirement.id)
        assert archived is not None
        self.assertFalse(archived.active)

        sanctions = legal_requirement_sanction_service.list_by_requirement(requirement.id)
        self.assertEqual(len(sanctions), 1)
        self.assertEqual(sanctions[0].id, sanction.id)

    def test_export_context_includes_sanctions(self) -> None:
        requirement = self._create_requirement()
        legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            authority="OIP",
            description="Exportovaná sankce",
            max_amount="10000",
        )

        context = legal_requirement_export_context_service.build_for_requirement(requirement.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(len(row.sanctions), 1)
        self.assertEqual(row.sanctions[0].authority, "OIP")
        self.assertEqual(row.sanctions[0].description, "Exportovaná sankce")
        self.assertIn("10", row.sanctions[0].max_amount)

    def test_create_sanction_requires_description(self) -> None:
        requirement = self._create_requirement()
        with self.assertRaises(ValueError):
            legal_requirement_sanction_service.create(
                requirement_id=requirement.id,
                description="   ",
            )

    def test_create_sanction_default_currency(self) -> None:
        requirement = self._create_requirement()
        sanction = legal_requirement_sanction_service.create(
            requirement_id=requirement.id,
            description="Výchozí měna",
            currency="",
        )
        self.assertEqual(sanction.currency, "Kč")


if __name__ == "__main__":
    unittest.main()
