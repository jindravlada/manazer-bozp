import importlib
import os
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
        DOCUMENT_TYPE_ZAKON,
        PERIODICITY_ROCNE,
        PROCESSING_NEW,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        legal_section_display_label,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_creation_service import (
        legal_requirement_creation_service,
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
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.ukoly.sluzby.task_service import task_service


class LegalRequirementServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for requirement in legal_requirement_service.get_all():
            requirement.active = False
            legal_requirement_service.repository.update(requirement)

    def _create_document(self, *, title: str = "Zákoník práce"):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

    def _create_version(self, document):
        return legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )

    def _create_section(self, document, version, **kwargs):
        defaults = {
            "legal_document_id": document.id,
            "legal_document_version_id": version.id,
            "section_type": SECTION_PARAGRAPH,
            "paragraph": "103",
            "title": "Školení zaměstnanců",
            "text": "Zaměstnavatel zajistí školení.",
            "sort_order": 10,
        }
        defaults.update(kwargs)
        return legal_section_service.create(**defaults)

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
        self.assertIsNone(row.legal_document_id)
        self.assertEqual(row.legal_document_title, "")
        self.assertIsNone(row.legal_section_id)
        self.assertEqual(row.legal_section_title, "")

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

    def test_requirement_can_link_to_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Zákoník práce",
            legal_document_id=document.id,
            requirement_summary="Test",
        )

        self.assertEqual(requirement.legal_document_id, document.id)

        updated = legal_requirement_service.get_by_id(requirement.id)
        assert updated is not None
        self.assertEqual(updated.legal_document_id, document.id)

    def test_requirement_can_exist_without_legal_document(self) -> None:
        requirement = self._create_requirement()
        self.assertIsNone(requirement.legal_document_id)

    def test_export_context_includes_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákon o BOZP",
            number="309/2006 Sb.",
            year=2006,
            short_title="BOZP",
        )
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Ruční název",
            legal_document_id=document.id,
            requirement_summary="Export test",
        )

        context = legal_requirement_export_context_service.build_for_requirement(requirement.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.legal_document_id, document.id)
        self.assertEqual(row.legal_document_title, "Zákon o BOZP")
        self.assertEqual(row.legal_document_short_title, "BOZP")
        self.assertEqual(row.legal_document_number, "309/2006 Sb.")
        self.assertEqual(row.legal_document_year, "2006")

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

    def test_requirement_can_link_to_legal_section(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Zákoník práce",
            legal_document_id=document.id,
            legal_section_id=section.id,
            requirement_summary="Test ustanovení",
        )

        self.assertEqual(requirement.legal_section_id, section.id)

        updated = legal_requirement_service.get_by_id(requirement.id)
        assert updated is not None
        self.assertEqual(updated.legal_section_id, section.id)

    def test_requirement_can_exist_without_legal_section(self) -> None:
        requirement = self._create_requirement()
        self.assertIsNone(requirement.legal_section_id)

    def test_requirement_cannot_link_to_missing_legal_section(self) -> None:
        with self.assertRaises(ValueError):
            legal_requirement_service.create_requirement(
                regulation_name="Test",
                legal_section_id=99999,
                requirement_summary="Neexistující ustanovení",
            )

    def test_requirement_cannot_link_to_inactive_legal_section(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        legal_section_service.deactivate(section.id)

        with self.assertRaises(ValueError):
            legal_requirement_service.create_requirement(
                regulation_name="Test",
                legal_section_id=section.id,
                requirement_summary="Neaktivní ustanovení",
            )

    def test_export_context_includes_legal_section(self) -> None:
        document = self._create_document(title="Zákon o BOZP")
        version = self._create_version(document)
        section = self._create_section(
            document,
            version,
            paragraph="103",
            section_number="2",
            item_letter="c",
            title="Školení zaměstnanců",
            text="Text ustanovení pro export",
        )
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Ruční název",
            legal_document_id=document.id,
            legal_section_id=section.id,
            requirement_summary="Export sekcí",
        )

        context = legal_requirement_export_context_service.build_for_requirement(requirement.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.legal_section_id, section.id)
        self.assertEqual(row.legal_section_type, "Paragraf")
        self.assertEqual(row.legal_section_paragraph, "103")
        self.assertEqual(row.legal_section_number, "2")
        self.assertEqual(row.legal_section_item_letter, "c")
        self.assertEqual(row.legal_section_title, "Školení zaměstnanců")
        self.assertEqual(row.legal_section_text, "Text ustanovení pro export")

    def test_section_selector_filters_by_document(self) -> None:
        first_document = self._create_document(title="První předpis")
        second_document = self._create_document(title="Druhý předpis")
        first_version = self._create_version(first_document)
        second_version = self._create_version(second_document)
        first_section = self._create_section(
            first_document,
            first_version,
            paragraph="10",
            title="První ustanovení",
        )
        second_section = self._create_section(
            second_document,
            second_version,
            paragraph="20",
            title="Druhé ustanovení",
        )

        all_sections = legal_section_service.list_for_selector()
        all_ids = {item.id for item in all_sections}
        self.assertIn(first_section.id, all_ids)
        self.assertIn(second_section.id, all_ids)

        first_only_ids = {
            item.id
            for item in legal_section_service.list_for_selector(document_id=first_document.id)
        }
        second_only_ids = {
            item.id
            for item in legal_section_service.list_for_selector(document_id=second_document.id)
        }
        self.assertIn(first_section.id, first_only_ids)
        self.assertNotIn(second_section.id, first_only_ids)
        self.assertIn(second_section.id, second_only_ids)
        self.assertNotIn(first_section.id, second_only_ids)

    def test_legal_section_display_label(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(
            document,
            version,
            paragraph="103",
            section_number="2",
            section_type=SECTION_SUBSECTION,
            item_letter="c",
            title="Školení zaměstnanců",
        )

        label = legal_section_display_label(section)
        self.assertEqual(label, "§ 103 odst. 2 písm. c) – Školení zaměstnanců")

    def test_create_draft_requirement_from_section(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)

        draft = legal_requirement_creation_service.create_from_section(section.id)

        self.assertIsNone(draft.id)
        self.assertEqual(draft.regulation_name, "Školení zaměstnanců")
        self.assertEqual(draft.requirement_summary, "")

    def test_draft_inherits_legal_document_id(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)

        draft = legal_requirement_creation_service.create_from_section(section.id)

        self.assertEqual(draft.legal_document_id, document.id)

    def test_draft_inherits_legal_section_id(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)

        draft = legal_requirement_creation_service.create_from_section(section.id)

        self.assertEqual(draft.legal_section_id, section.id)

    def test_draft_sets_source_section_id(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)

        draft = legal_requirement_creation_service.create_from_section(section.id)

        self.assertEqual(draft.source_section_id, section.id)

    def test_draft_processing_status_is_new(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)

        draft = legal_requirement_creation_service.create_from_section(section.id)

        self.assertEqual(draft.processing_status, PROCESSING_NEW)

    def test_saved_requirement_from_section_keeps_source_link(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        draft = legal_requirement_creation_service.create_from_section(section.id)

        requirement = legal_requirement_service.create_requirement(
            regulation_name=draft.regulation_name,
            regulation_number=draft.regulation_number,
            provision=draft.provision,
            legal_document_id=draft.legal_document_id,
            legal_section_id=draft.legal_section_id,
            source_section_id=draft.source_section_id,
            requirement_summary="Zajistit školení zaměstnanců",
            processing_status=draft.processing_status,
        )

        saved = legal_requirement_service.get_by_id(requirement.id)
        assert saved is not None
        self.assertTrue(saved.active)
        self.assertEqual(saved.source_section_id, section.id)
        self.assertEqual(saved.legal_section_id, section.id)
        listed_ids = [item.id for item in legal_requirement_service.get_all()]
        self.assertIn(saved.id, listed_ids)

    def test_structure_tree_shows_requirement_column_after_create_from_section(self) -> None:
        from PySide6.QtCore import Qt

        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        draft = legal_requirement_creation_service.create_from_section(section.id)

        legal_requirement_service.create_requirement(
            regulation_name=draft.regulation_name,
            regulation_number=draft.regulation_number,
            provision=draft.provision,
            legal_document_id=draft.legal_document_id,
            legal_section_id=draft.legal_section_id,
            source_section_id=draft.source_section_id,
            requirement_summary="Zajistit školení zaměstnanců",
            processing_status=draft.processing_status,
        )

        sections = legal_section_service.list_by_version(version.id)
        sections_with_requirements = legal_requirement_service.get_source_section_ids(
            [section.id],
        )
        self.assertIn(section.id, sections_with_requirements)

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from moduly.pravni_pozadavky.ui.legal_section_tree import LegalSectionTree

        tree = LegalSectionTree()
        tree.load_sections(sections, sections_with_requirements=sections_with_requirements)

        requirement_value = None
        for index in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(index)
            if item.data(LegalSectionTree.COLUMN_ID, Qt.ItemDataRole.UserRole) == section.id:
                requirement_value = item.text(LegalSectionTree.COLUMN_REQUIREMENT)
                break

        self.assertEqual(requirement_value, "Ano")

    def test_section_table_detects_existing_requirement(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section_with_requirement = self._create_section(
            document,
            version,
            paragraph="1",
            title="S požadavkem",
        )
        section_without_requirement = self._create_section(
            document,
            version,
            paragraph="2",
            title="Bez požadavku",
        )
        legal_requirement_service.create_requirement(
            regulation_name="Test",
            legal_document_id=document.id,
            legal_section_id=section_with_requirement.id,
            source_section_id=section_with_requirement.id,
            requirement_summary="Požadavek ze sekce",
        )

        linked_section_ids = legal_requirement_service.get_source_section_ids(
            [section_with_requirement.id, section_without_requirement.id],
        )

        self.assertIn(section_with_requirement.id, linked_section_ids)
        self.assertNotIn(section_without_requirement.id, linked_section_ids)

    def test_export_context_includes_processing_fields(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Test",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
            requirement_summary="Export stavu zpracování",
            processing_status=PROCESSING_NEW,
        )

        context = legal_requirement_export_context_service.build_for_requirement(requirement.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.source_section_id, section.id)
        self.assertEqual(row.processing_status, PROCESSING_NEW)
        self.assertEqual(row.processing_status_label, "Nový")


if __name__ == "__main__":
    unittest.main()
