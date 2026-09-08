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
        CHANGE_SECTION_REMOVED,
        DOCUMENT_TYPE_ZAKON,
        SECTION_LETTER,
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

    def test_lists_only_changed_legal_sources_of_process(self) -> None:
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
        self.assertEqual(len(processes[0].legal_sources), 1)
        source = processes[0].legal_sources[0]
        self.assertEqual(source.label, "§104")
        self.assertEqual(source.change_type, CHANGE_SECTION_MODIFIED)
        self.assertEqual(source.display_label, "§104 – změněno")
        self.assertTrue(source.is_changed)

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

    def test_hides_process_without_link_to_changed_section(self) -> None:
        document, version, _paragraph, _subsection = self._create_document_with_subsection()
        paragraph_101 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="§ 101",
            sort_order=0,
        )
        legal_requirement_service.create_requirement(
            title="Školení BOZP",
            process_code="P-015",
            source_section_ids=[paragraph_101.id],
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[SectionStructureEntry("§:104", "§104", "fp1")],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(processes, [])

    def test_process_with_many_sources_shows_only_the_changed_one(self) -> None:
        document, version, _paragraph, _subsection = self._create_document_with_subsection()
        source_ids = []
        for number in range(1, 11):
            section = legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=SECTION_PARAGRAPH,
                paragraph=str(number),
                title=f"§ {number}",
                sort_order=number,
            )
            source_ids.append(section.id)
        legal_requirement_service.create_requirement(
            title="Řízení dokumentace",
            process_code="P-001",
            source_section_ids=source_ids,
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[SectionStructureEntry("§:7", "§7", "fp7")],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(len(processes), 1)
        self.assertEqual([source.label for source in processes[0].legal_sources], ["§7"])
        self.assertEqual(processes[0].legal_sources[0].display_label, "§7 – změněno")

    def test_two_changed_sections_of_same_process_are_listed_once(self) -> None:
        document, version, paragraph, _subsection = self._create_document_with_subsection()
        paragraph_101 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="§ 101",
            sort_order=0,
        )
        legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
            source_section_ids=[paragraph.id, paragraph_101.id],
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                changed=[
                    SectionStructureEntry("§:104", "§104", "fp1"),
                    SectionStructureEntry("§:101", "§101", "fp2"),
                ],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(len(processes), 1)
        self.assertEqual(
            [source.display_label for source in processes[0].legal_sources],
            ["§101 – změněno", "§104 – změněno"],
        )

    def test_removed_parent_with_unlinked_children_shows_only_parent(self) -> None:
        document, version, paragraph, _subsection = self._create_document_with_subsection()
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=paragraph.id,
            item_letter="a",
            title="písm. a)",
            sort_order=3,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=paragraph.id,
            item_letter="b",
            title="písm. b)",
            sort_order=4,
        )
        legal_requirement_service.create_requirement(
            title="Řízení pracovního prostředí",
            process_code="P-012",
            source_section_ids=[paragraph.id],
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                removed=[
                    SectionStructureEntry("§:104", "§104", "fp1"),
                    SectionStructureEntry("§:104/pism:a", "§104 písm.a)", "fp2"),
                    SectionStructureEntry("§:104/pism:b", "§104 písm.b)", "fp3"),
                ],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(len(processes), 1)
        self.assertEqual(
            [source.display_label for source in processes[0].legal_sources],
            ["§104 – zrušeno"],
        )

    def test_added_section_without_link_does_not_create_false_impact(self) -> None:
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
                new=[SectionStructureEntry("§:12b", "§12b", "fp-new")],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(processes, [])

    def test_nv_361_2007_process_p012_shows_only_removed_section_12a(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Nařízení vlády o ochraně zdraví při práci",
            number="361/2007 Sb.",
            year=2007,
            short_title="NV 361/2007",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        source_ids = []
        for number in (2, 3, 4, 5, 12, 13):
            section = legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=SECTION_PARAGRAPH,
                paragraph=str(number),
                title=f"§ {number}",
                sort_order=number,
            )
            source_ids.append(section.id)
        paragraph_12a = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12a",
            title="§ 12a",
            sort_order=12,
        )
        source_ids.append(paragraph_12a.id)
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=paragraph_12a.id,
            item_letter="a",
            title="písm. a)",
            sort_order=20,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=paragraph_12a.id,
            item_letter="b",
            title="písm. b)",
            sort_order=21,
        )
        legal_requirement_service.create_requirement(
            title="Řízení pracovního prostředí",
            process_code="P-012",
            source_section_ids=source_ids,
        )
        change = self._create_change(document, version)
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                removed=[
                    SectionStructureEntry("§:12a", "§12a", "fp12a"),
                    SectionStructureEntry("§:12a/pism:a", "§12a písm.a)", "fp12aa"),
                    SectionStructureEntry("§:12a/pism:b", "§12a písm.b)", "fp12ab"),
                ],
            ),
        )

        processes = legal_change_impacted_process_service.list_processes_for_change(change.id)

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].display_title, "P-012 Řízení pracovního prostředí")
        self.assertEqual(
            [source.display_label for source in processes[0].legal_sources],
            ["§12a – zrušeno"],
        )
        shown_labels = {source.label for source in processes[0].legal_sources}
        self.assertNotIn("§2", shown_labels)
        self.assertNotIn("§3", shown_labels)
        self.assertNotIn("§4", shown_labels)
        self.assertNotIn("§12a písm.a)", shown_labels)
        self.assertNotIn("§12a písm.b)", shown_labels)
        self.assertEqual(processes[0].legal_sources[0].change_type, CHANGE_SECTION_REMOVED)


if __name__ == "__main__":
    unittest.main()
