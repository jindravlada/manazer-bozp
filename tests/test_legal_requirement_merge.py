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

    from core.shared.constants import ENTITY_LEGAL_REQUIREMENT, ENTITY_RISK, LINK_LEGAL_BASIS
    from core.shared.sluzby.entity_link_service import entity_link_service
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_NESPLNENO,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_sanction_service import (
        legal_requirement_sanction_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRequirementMergeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_document(self):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

    def _create_version(self, document):
        return legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )

    def _create_subsections(self, document, version, count: int):
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        sections = []
        for index in range(1, count + 1):
            sections.append(
                legal_section_service.create(
                    legal_document_id=document.id,
                    legal_document_version_id=version.id,
                    section_type=SECTION_SUBSECTION,
                    parent_section_id=paragraph.id,
                    section_number=str(index),
                    text=f"Text odstavce {index}",
                    sort_order=index,
                )
            )
        return sections

    def test_merge_p004_into_p002_moves_sources_and_archives_source(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_subsections(document, version, 3)

        target = legal_requirement_service.create_requirement(
            title="Prevence rizik",
            regulation_name="Zákoník práce",
            legal_document_id=document.id,
            legal_section_id=sections[0].id,
            source_section_id=sections[0].id,
            requirement_summary="Cílový proces",
        )
        source = legal_requirement_service.create_requirement(
            title="Kontrola dokumentace",
            regulation_name="Zákoník práce",
            legal_document_id=document.id,
            legal_section_id=sections[1].id,
            source_section_ids=[sections[1].id, sections[2].id],
            requirement_summary="Zdrojový proces",
            compliance_status=COMPLIANCE_NESPLNENO,
        )
        legal_requirement_service.record_verification(
            source.id,
            check_date=date(2026, 1, 15),
            result=COMPLIANCE_NESPLNENO,
            comment="Kontrola P-004",
        )
        legal_requirement_sanction_service.create(
            requirement_id=source.id,
            authority="OIP",
            description="Sankce P-004",
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_REQUIREMENT,
            source_id=source.id,
            target_type=ENTITY_RISK,
            target_id=42,
            link_type=LINK_LEGAL_BASIS,
            note="Vazba P-004",
        )

        merged = legal_requirement_service.merge_process_requirements(source.id, target.id)

        self.assertEqual(merged.id, target.id)
        self.assertEqual(
            legal_requirement_service.list_source_section_ids_for_requirement(target.id),
            [sections[0].id, sections[1].id, sections[2].id],
        )
        self.assertEqual(len(legal_requirement_service.get_checks(target.id)), 1)
        self.assertEqual(legal_requirement_service.get_checks(target.id)[0].comment, "Kontrola P-004")

        sanctions = legal_requirement_sanction_service.list_by_requirement(
            target.id,
            include_inactive=True,
        )
        self.assertEqual(len(sanctions), 1)
        self.assertEqual(sanctions[0].description, "Sankce P-004")

        links = entity_link_service.list_for_source(ENTITY_LEGAL_REQUIREMENT, target.id)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].target_id, 42)
        self.assertEqual(links[0].note, "Vazba P-004")

        archived_source = legal_requirement_service.get_by_id(source.id)
        assert archived_source is not None
        self.assertFalse(archived_source.active)
        self.assertEqual(archived_source.merged_into_requirement_id, target.id)
        self.assertEqual(archived_source.process_code, source.process_code)

        active_processes = legal_requirement_service.list_active_processes()
        active_codes = [item.process_code for item in active_processes]
        self.assertIn(target.process_code, active_codes)
        self.assertNotIn(source.process_code, active_codes)

    def test_merge_does_not_create_duplicate_sources(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_subsections(document, version, 1)
        section = sections[0]

        target = legal_requirement_service.create_requirement(
            title="P-002",
            source_section_id=section.id,
            requirement_summary="Cíl",
        )
        source = legal_requirement_service.create_requirement(
            title="P-004",
            source_section_id=section.id,
            requirement_summary="Zdroj",
        )

        legal_requirement_service.merge_process_requirements(source.id, target.id)

        merged_sources = legal_requirement_service.list_source_section_ids_for_requirement(
            target.id,
        )
        self.assertEqual(merged_sources, [section.id])

    def test_merge_rejects_same_process(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="P-002",
            requirement_summary="Test",
        )

        with self.assertRaisesRegex(ValueError, "různé"):
            legal_requirement_service.merge_process_requirements(requirement.id, requirement.id)

    def test_merge_rejects_archived_source(self) -> None:
        target = legal_requirement_service.create_requirement(title="P-002", requirement_summary="Cíl")
        source = legal_requirement_service.create_requirement(title="P-004", requirement_summary="Zdroj")
        legal_requirement_service.archive_requirement(source.id)

        with self.assertRaisesRegex(ValueError, "aktivní"):
            legal_requirement_service.merge_process_requirements(source.id, target.id)


if __name__ == "__main__":
    unittest.main()
