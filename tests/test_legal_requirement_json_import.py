import importlib
import json
import tempfile
import unittest
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
        DOCUMENT_TYPE_ZAKON,
        PROCESSING_NEW,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.import_export.legal_requirement_json_import_service import (
        ALL_SOURCES_ALREADY_LINKED_MESSAGE,
        DUPLICATE_SKIP_MESSAGE,
        REQUIREMENT_IMPORT_STATUS_CREATED,
        REQUIREMENT_IMPORT_STATUS_ERROR,
        REQUIREMENT_IMPORT_STATUS_EXTENDED,
        REQUIREMENT_IMPORT_STATUS_OK,
        REQUIREMENT_IMPORT_STATUS_SKIPPED,
        legal_requirement_json_import_service,
        normalize_provision_label,
        parse_import_items,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRequirementJsonImportTestCase(unittest.TestCase):
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

        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )
        self.version = legal_document_version_service.create(
            legal_document_id=self.document.id,
            version_name="Aktuální znění",
        )
        paragraph = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        self.subsection = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Zaměstnavatel je povinen zajistit bezpečnost a ochranu zdraví zaměstnanců při práci.",
            sort_order=2,
        )

    def _import_item(self, **overrides):
        payload = {
            "document_number": "262",
            "document_year": 2006,
            "provision_label": "§ 101 odst. 1",
            "title": "Bezpečnost práce",
            "fulfillment_text": "Zajistit bezpečnost práce.",
            "note": "Import test",
            "processing_status": "new",
        }
        payload.update(overrides)
        return legal_requirement_json_import_service.import_items(
            parse_import_items([payload]),
        )

    def test_parse_import_items_reads_required_fields(self) -> None:
        items = parse_import_items([
            {
                "document_number": "262",
                "document_year": 2006,
                "provision_label": "§ 101 odst. 1",
                "title": "Test",
                "fulfillment_text": "Text",
                "note": "Poznámka",
                "processing_status": "approved",
            },
        ])

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].document_number, "262")
        self.assertEqual(items[0].provision_label, "§ 101 odst. 1")
        self.assertEqual(items[0].processing_status, "approved")

    def test_normalize_provision_label_matches_section_label(self) -> None:
        sections = legal_section_service.list_by_version(self.version.id)
        sections_by_id = legal_section_service.build_sections_map(sections)
        from moduly.pravni_pozadavky.constants import legal_section_provision_label

        label = legal_section_provision_label(self.subsection, sections_by_id=sections_by_id)
        self.assertEqual(normalize_provision_label("§ 101 odst. 1"), label)

    def test_import_creates_requirement_for_existing_section(self) -> None:
        summary = self._import_item()

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.created_count, 1)
        self.assertEqual(summary.extended_count, 0)
        self.assertEqual(summary.error_count, 0)
        self.assertEqual(summary.skipped_count, 0)
        self.assertEqual(summary.ok_count, 1)

        saved = legal_requirement_service.get_by_source_section_id(self.subsection.id)
        assert saved is not None
        self.assertEqual(saved.title, "Bezpečnost práce")
        self.assertEqual(saved.regulation_name, "Zákoník práce")
        self.assertEqual(saved.requirement_summary, "Zajistit bezpečnost práce.")
        self.assertEqual(saved.processing_status, PROCESSING_NEW)
        self.assertEqual(saved.source_section_id, self.subsection.id)
        self.assertEqual(
            legal_requirement_service.list_source_section_ids_for_requirement(saved.id),
            [self.subsection.id],
        )

    def test_import_skips_existing_requirement(self) -> None:
        self._import_item()
        summary = self._import_item(title="Jiný název")

        self.assertEqual(summary.created_count, 0)
        self.assertEqual(summary.ok_count, 0)
        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.rows[0].status, REQUIREMENT_IMPORT_STATUS_SKIPPED)
        self.assertEqual(summary.rows[0].error, DUPLICATE_SKIP_MESSAGE)

    def test_import_continues_after_error(self) -> None:
        summary = legal_requirement_json_import_service.import_items(
            parse_import_items([
                {
                    "document_number": "999",
                    "document_year": 2099,
                    "provision_label": "§ 1",
                    "title": "Chybný",
                },
                {
                    "document_number": "262",
                    "document_year": 2006,
                    "provision_label": "§ 101 odst. 1",
                    "title": "Správný",
                    "fulfillment_text": "Text",
                },
            ]),
        )

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.error_count, 1)
        self.assertEqual(summary.created_count, 1)
        self.assertEqual(summary.ok_count, 1)
        self.assertEqual(summary.rows[0].status, REQUIREMENT_IMPORT_STATUS_ERROR)
        self.assertEqual(summary.rows[1].status, REQUIREMENT_IMPORT_STATUS_CREATED)
        self.assertEqual(REQUIREMENT_IMPORT_STATUS_OK, REQUIREMENT_IMPORT_STATUS_CREATED)

    def test_import_from_file_returns_summary_counts(self) -> None:
        sample_path = Path(__file__).resolve().parent / "data" / "sample_legal_requirements_import.json"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(
                [
                    {
                        "document_number": "262",
                        "document_year": 2006,
                        "provision_label": "§ 101 odst. 1",
                        "title": "Z JSON souboru",
                        "fulfillment_text": "Text z JSON",
                    },
                    {
                        "document_number": "262",
                        "document_year": 2006,
                        "provision_label": "§ 101 odst. 1",
                        "title": "Duplicitní",
                    },
                ],
                handle,
                ensure_ascii=False,
            )
            temp_path = handle.name

        try:
            summary = legal_requirement_json_import_service.import_from_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.created_count, 1)
        self.assertEqual(summary.ok_count, 1)
        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.error_count, 0)

        saved = legal_requirement_service.get_by_source_section_id(self.subsection.id)
        assert saved is not None
        self.assertEqual(saved.title, "Z JSON souboru")
        self.assertEqual(saved.regulation_name, "Zákoník práce")

        _ = sample_path

    def test_parse_import_items_reads_process_code(self) -> None:
        items = parse_import_items([
            {
                "document_number": "262",
                "document_year": 2006,
                "provision_label": "§ 101 odst. 1",
                "process_code": "P-003",
                "title": "Řízení rizik",
                "fulfillment_text": "Text",
            },
        ])

        self.assertEqual(items[0].process_code, "P-003")

    def test_import_with_process_code_extends_existing_process(self) -> None:
        existing = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            requirement_summary="Původní plnění",
            note="Původní poznámka",
            processing_status=PROCESSING_NEW,
        )
        existing.process_code = "P-003"
        from core.database.session import get_session

        with get_session() as session:
            session.merge(existing)
            session.commit()

        nv_document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Nařízení vlády",
            number="390",
            year=2021,
            short_title="NV",
        )
        nv_version = legal_document_version_service.create(
            legal_document_id=nv_document.id,
            version_name="Verze",
        )
        nv_paragraph = legal_section_service.create(
            legal_document_id=nv_document.id,
            legal_document_version_id=nv_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            title="OOPP",
            sort_order=1,
        )
        nv_section = legal_section_service.create(
            legal_document_id=nv_document.id,
            legal_document_version_id=nv_version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=nv_paragraph.id,
            section_number="2",
            text="NV text",
            sort_order=2,
        )

        summary = legal_requirement_json_import_service.import_items(
            parse_import_items([
                {
                    "document_number": "390",
                    "document_year": 2021,
                    "provision_label": "§ 5 odst. 2",
                    "process_code": "P-003",
                    "title": "Jiný název z JSON",
                    "fulfillment_text": "Nové plnění",
                    "note": "Nová poznámka",
                    "sources": [
                        {
                            "document_number": "390",
                            "document_year": 2021,
                            "provision_label": "§ 5 odst. 2",
                        },
                    ],
                },
            ]),
        )

        self.assertEqual(summary.extended_count, 1)
        self.assertEqual(summary.created_count, 0)
        self.assertEqual(summary.rows[0].status, REQUIREMENT_IMPORT_STATUS_EXTENDED)

        refreshed = legal_requirement_service.get_by_id(existing.id)
        assert refreshed is not None
        self.assertEqual(refreshed.title, "Řízení rizik")
        self.assertEqual(refreshed.process_code, "P-003")
        self.assertEqual(refreshed.requirement_summary, "Nové plnění")
        self.assertEqual(refreshed.note, "Nová poznámka")
        section_ids = legal_requirement_service.list_source_section_ids_for_requirement(refreshed.id)
        self.assertEqual(section_ids, [nv_section.id])

    def test_import_with_process_code_skips_when_all_sources_already_linked(self) -> None:
        existing = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            legal_document_id=self.document.id,
            legal_section_id=self.subsection.id,
            source_section_id=self.subsection.id,
            source_section_ids=[self.subsection.id],
            requirement_summary="Text",
        )
        existing.process_code = "P-004"
        from core.database.session import get_session

        with get_session() as session:
            session.merge(existing)
            session.commit()

        summary = self._import_item(process_code="P-004")

        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.extended_count, 0)
        self.assertEqual(summary.rows[0].error, ALL_SOURCES_ALREADY_LINKED_MESSAGE)

    def test_import_with_process_code_creates_when_process_missing(self) -> None:
        summary = self._import_item(process_code="P-010", title="Nový proces")

        self.assertEqual(summary.created_count, 1)
        self.assertEqual(summary.extended_count, 0)
        saved = legal_requirement_service.get_by_source_section_id(self.subsection.id)
        assert saved is not None
        self.assertEqual(saved.process_code, "P-010")
        self.assertEqual(saved.title, "Nový proces")

    def test_import_with_process_code_does_not_overwrite_empty_metadata(self) -> None:
        existing = legal_requirement_service.create_requirement(
            title="Řízení kompetencí",
            requirement_summary="Původní plnění",
            note="Původní poznámka",
        )
        existing.process_code = "P-005"
        from core.database.session import get_session

        with get_session() as session:
            session.merge(existing)
            session.commit()

        summary = legal_requirement_json_import_service.import_items(
            parse_import_items([
                {
                    "document_number": "262",
                    "document_year": 2006,
                    "provision_label": "§ 101 odst. 1",
                    "process_code": "P-005",
                    "title": "Jiný název",
                    "fulfillment_text": "",
                    "note": "",
                    "sources": [
                        {
                            "document_number": "262",
                            "document_year": 2006,
                            "provision_label": "§ 101 odst. 1",
                        },
                    ],
                },
            ]),
        )

        self.assertEqual(summary.extended_count, 1)
        refreshed = legal_requirement_service.get_by_id(existing.id)
        assert refreshed is not None
        self.assertEqual(refreshed.requirement_summary, "Původní plnění")
        self.assertEqual(refreshed.note, "Původní poznámka")

    def test_import_with_process_code_errors_when_source_linked_to_other_process(self) -> None:
        other = legal_requirement_service.create_requirement(
            title="Jiný proces",
            legal_document_id=self.document.id,
            legal_section_id=self.subsection.id,
            source_section_id=self.subsection.id,
            source_section_ids=[self.subsection.id],
        )
        existing = legal_requirement_service.create_requirement(title="Cílový proces")
        existing.process_code = "P-006"
        from core.database.session import get_session

        with get_session() as session:
            session.merge(existing)
            session.commit()

        summary = self._import_item(process_code="P-006")

        self.assertEqual(summary.error_count, 1)
        self.assertEqual(summary.rows[0].status, REQUIREMENT_IMPORT_STATUS_ERROR)
        self.assertIn("jinému procesu", summary.rows[0].error.lower())
        _ = other


if __name__ == "__main__":
    unittest.main()
