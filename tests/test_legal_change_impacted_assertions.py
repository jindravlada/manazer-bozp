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

    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.pravni_pozadavky.constants import (
        CHANGE_NOVELIZATION,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_impacted_assertion_service import (
        legal_change_impacted_assertion_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
        legal_change_section_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
        SectionStructureCompareResult,
        SectionStructureEntry,
    )


class LegalChangeImpactedAssertionServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_document_with_subsection(self):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="104",
            title="§ 104",
            sort_order=1,
        )
        subsection = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            title="odst. 1",
            sort_order=2,
        )
        return document, version, paragraph, subsection

    def _create_change(self, document, version):
        run = legal_check_run_service.create(
            title="Kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
        )
        return legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            legal_check_run_id=run.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
        )

    def test_lists_audit_assertions_for_impacted_process(self) -> None:
        document, version, paragraph, _subsection = self._create_document_with_subsection()
        legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
            source_section_ids=[paragraph.id],
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[SectionStructureEntry("§:104", "§104", "fp1")],
            ),
        )

        assertions = legal_change_impacted_assertion_service.list_assertions_for_change(change.id)

        self.assertGreater(len(assertions), 0)
        self.assertTrue(all(item.process_code == "P-005" for item in assertions))
        self.assertTrue(all(item.process_name == "Řízení rizik" for item in assertions))
        self.assertTrue(all(item.text for item in assertions))
        self.assertIn("id_proces_identifikace", {item.assertion_id for item in assertions})

    def test_returns_empty_when_process_has_no_matching_audit_methodology(self) -> None:
        document, version, paragraph, _subsection = self._create_document_with_subsection()
        legal_requirement_service.create_requirement(
            title="Neexistující proces",
            process_code="P-999",
            source_section_ids=[paragraph.id],
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[SectionStructureEntry("§:104", "§104", "fp1")],
            ),
        )

        assertions = legal_change_impacted_assertion_service.list_assertions_for_change(change.id)

        self.assertEqual(assertions, [])

    def test_returns_empty_when_change_has_no_impacted_processes(self) -> None:
        document, version, _, _ = self._create_document_with_subsection()
        change = self._create_change(document, version)

        assertions = legal_change_impacted_assertion_service.list_assertions_for_change(change.id)

        self.assertEqual(assertions, [])


if __name__ == "__main__":
    unittest.main()
