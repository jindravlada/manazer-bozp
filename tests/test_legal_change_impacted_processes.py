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
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
        legal_change_impacted_process_service,
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


class LegalChangeImpactedProcessServiceTestCase(unittest.TestCase):
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

    def test_finds_processes_linked_to_changed_sections(self) -> None:
        document, version, paragraph, subsection = self._create_document_with_subsection()
        process_one = legal_requirement_service.create_requirement(
            title="Řízení pracovních úrazů",
            process_code="P-12",
            source_section_ids=[paragraph.id],
        )
        process_two = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            process_code="P-15",
            source_section_ids=[subsection.id],
        )
        change = self._create_change(document, version)
        compare_result = SectionStructureCompareResult(
            changed=[
                SectionStructureEntry("§:104", "§104", "fp1"),
                SectionStructureEntry("§:104/odst:1", "§104 odst.1", "fp2"),
            ],
        )
        legal_change_section_service.add_sections_to_change(change.id, compare_result)

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(len(processes), 2)
        self.assertEqual(
            {(item.process_code, item.process_name) for item in processes},
            {
                (process_one.process_code, process_one.title),
                (process_two.process_code, process_two.title),
            },
        )

    def test_lists_legal_sources_and_marks_changed_sections(self) -> None:
        document, version, paragraph, subsection = self._create_document_with_subsection()
        paragraph_101 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="§ 101",
            sort_order=0,
        )
        process = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
            source_section_ids=[paragraph.id, paragraph_101.id],
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[SectionStructureEntry("§:104", "§104", "fp1")],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].process_code, process.process_code)
        self.assertEqual(len(processes[0].legal_sources), 2)
        changed = [source for source in processes[0].legal_sources if source.is_changed]
        unchanged = [source for source in processes[0].legal_sources if not source.is_changed]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0].label, "§104")
        self.assertEqual(len(unchanged), 1)
        self.assertEqual(unchanged[0].label, "§101")

    def test_returns_empty_when_no_linked_processes(self) -> None:
        document, version, _, _subsection = self._create_document_with_subsection()
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[SectionStructureEntry("§:104", "§104", "fp1")],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(processes, [])

    def test_returns_empty_when_change_has_no_sections(self) -> None:
        document, version, _, _ = self._create_document_with_subsection()
        change = self._create_change(document, version)

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(processes, [])


if __name__ == "__main__":
    unittest.main()
