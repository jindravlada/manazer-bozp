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

    from moduly.pravni_pozadavky.constants import (
        CHANGE_NOVELIZATION,
        CHANGE_SECTION_MODIFIED,
        DOCUMENT_TYPE_ZAKON,
        PROCESSING_APPROVED,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.modely.legal_change import LegalChange
    from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
    from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
    from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.modely.legal_section import LegalSection
    from moduly.pravni_pozadavky.repository.legal_change_repository import LegalChangeRepository
    from moduly.pravni_pozadavky.repository.legal_change_section_repository import (
        LegalChangeSectionRepository,
    )
    from moduly.pravni_pozadavky.repository.legal_check_run_repository import (
        LegalCheckRunRepository,
    )
    from moduly.pravni_pozadavky.repository.legal_document_version_repository import (
        LegalDocumentVersionRepository,
    )
    from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
        LegalRequirementSourceRepository,
    )
    from moduly.pravni_pozadavky.repository.legal_section_repository import LegalSectionRepository
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_registry_diagnostic_service import (
        legal_registry_diagnostic_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRegistryDiagnosticServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._clear_registry_tables()

    def _clear_registry_tables(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_sanction import (
            LegalRequirementSanction,
        )
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalRequirementSanction))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def test_empty_registry_is_consistent(self) -> None:
        result = legal_registry_diagnostic_service.run()

        self.assertTrue(result.is_consistent)
        self.assertEqual(result.issue_count, 0)
        self.assertEqual(result.stats.document_count, 0)
        self.assertEqual(result.stats.version_count, 0)
        self.assertEqual(result.stats.section_count, 0)
        self.assertEqual(result.stats.requirement_count, 0)
        self.assertEqual(result.stats.processes_without_sources_count, 0)
        self.assertEqual(result.stats.source_count, 0)
        self.assertEqual(result.stats.sanction_count, 0)
        self.assertEqual(result.stats.check_run_count, 0)
        self.assertEqual(result.stats.change_count, 0)
        self.assertEqual(result.stats.change_section_count, 0)

        report = legal_registry_diagnostic_service.format_report(result)
        self.assertIn("✔ Registr je konzistentní.", report)

    def test_consistent_registry_reports_statistics(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="103",
            title="Školení zaměstnanců",
            text="Zaměstnavatel zajistí školení.",
            sort_order=10,
        )
        requirement = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            process_code="P-001",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
            processing_status=PROCESSING_APPROVED,
        )
        legal_requirement_service.attach_source_section(requirement.id, section.id)
        run = legal_check_run_service.create(
            title="Kontrola 1/2026",
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            legal_section_id=section.id,
            legal_check_run_id=run.id,
            change_type=CHANGE_NOVELIZATION,
            title="Novelizace zákona",
        )
        LegalChangeSectionRepository().create(
            LegalChangeSection(
                legal_change_id=change.id,
                section_key="§:103",
                section_label="§ 103",
                change_type=CHANGE_SECTION_MODIFIED,
            ),
        )

        result = legal_registry_diagnostic_service.run()

        self.assertTrue(result.is_consistent)
        self.assertEqual(result.stats.document_count, 1)
        self.assertEqual(result.stats.version_count, 1)
        self.assertEqual(result.stats.section_count, 1)
        self.assertEqual(result.stats.requirement_count, 1)
        self.assertEqual(result.stats.processes_without_sources_count, 0)
        self.assertEqual(result.stats.source_count, 1)
        self.assertEqual(result.stats.check_run_count, 1)
        self.assertEqual(result.stats.change_count, 1)
        self.assertEqual(result.stats.change_section_count, 1)

        report = legal_registry_diagnostic_service.format_report(result)
        self.assertIn("Právní předpisy", report)
        self.assertIn("Řídicí procesy", report)
        self.assertIn("✔ Registr je konzistentní.", report)

    def test_process_without_sources_is_reported(self) -> None:
        legal_requirement_service.create_requirement(
            title="Proces bez podkladů",
            process_code="P-005",
        )

        result = legal_registry_diagnostic_service.run()

        self.assertFalse(result.is_consistent)
        self.assertEqual(result.stats.processes_without_sources_count, 1)
        self.assertIn("Proces P-005 nemá žádný právní podklad.", result.issues)

    def test_invalid_foreign_key_links_are_reported(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="103",
            title="Školení zaměstnanců",
            text="Zaměstnavatel zajistí školení.",
            sort_order=10,
        )
        requirement = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            process_code="P-001",
        )

        source_repository = LegalRequirementSourceRepository()
        invalid_source = source_repository.create(
            LegalRequirementSource(
                requirement_id=9999,
                legal_section_id=section.id,
                sort_order=1,
            ),
        )
        orphan_source = source_repository.create(
            LegalRequirementSource(
                requirement_id=requirement.id,
                legal_section_id=9999,
                sort_order=1,
            ),
        )

        orphan_section = LegalSectionRepository().create(
            LegalSection(
                legal_document_id=document.id,
                legal_document_version_id=9999,
                section_type=SECTION_PARAGRAPH,
                paragraph="999",
                title="Orphan",
                text="Text",
                sort_order=99,
            ),
        )

        orphan_version = LegalDocumentVersion(
            legal_document_id=9999,
            version_name="Orphan verze",
        )
        orphan_version = LegalDocumentVersionRepository().create(orphan_version)

        orphan_change = LegalChange(
            legal_document_id=document.id,
            legal_check_run_id=9999,
            change_type=CHANGE_NOVELIZATION,
            title="Změna bez kontroly",
        )
        orphan_change = LegalChangeRepository().create(orphan_change)

        orphan_change_section = LegalChangeSection(
            legal_change_id=9999,
            section_key="§:1",
            section_label="§ 1",
            change_type=CHANGE_SECTION_MODIFIED,
        )
        orphan_change_section = LegalChangeSectionRepository().create(orphan_change_section)

        result = legal_registry_diagnostic_service.run()

        self.assertFalse(result.is_consistent)
        self.assertIn(
            f"Právní podklad ID {invalid_source.id} odkazuje na neexistující proces.",
            result.issues,
        )
        self.assertIn(
            f"Právní podklad ID {orphan_source.id} odkazuje na neexistující ustanovení.",
            result.issues,
        )
        self.assertIn(
            f"Ustanovení ID {orphan_section.id} odkazuje na neexistující verzi předpisu.",
            result.issues,
        )
        self.assertIn(
            f"Verze předpisu ID {orphan_version.id} odkazuje na neexistující právní předpis.",
            result.issues,
        )
        self.assertIn(
            f"Změna ID {orphan_change.id} odkazuje na neexistující kontrolu změn.",
            result.issues,
        )
        self.assertIn(
            f"Změněné ustanovení ID {orphan_change_section.id} odkazuje na neexistující změnu.",
            result.issues,
        )

        report = legal_registry_diagnostic_service.format_report(result)
        self.assertIn(f"⚠ Bylo nalezeno {result.issue_count} problémů.", report)


if __name__ == "__main__":
    unittest.main()
