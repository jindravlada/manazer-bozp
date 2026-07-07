import importlib
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
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_ZAKON,
        PROCESSING_APPROVED,
        PROCESSING_NEW,
        REQUIREMENT_STATUS_APPROVED,
        REQUIREMENT_STATUS_EXISTS,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.import_export.legal_requirement_json_import_service import (
        DUPLICATE_SKIP_MESSAGE,
        REQUIREMENT_IMPORT_STATUS_OK,
        REQUIREMENT_IMPORT_STATUS_SKIPPED,
        legal_requirement_json_import_service,
        parse_import_items,
    )
    from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
        LegalRequirementSourceRepository,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRequirementSourcesTestCase(unittest.TestCase):
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

        self.source_repository = LegalRequirementSourceRepository()

    def _create_document(
        self,
        *,
        title: str,
        number: str,
        year: int,
        short_title: str,
    ):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number=number,
            year=year,
            short_title=short_title,
        )

    def _create_subsection(
        self,
        document,
        version,
        *,
        paragraph: str = "104",
        section_number: str = "1",
        sort_order: int = 1,
    ):
        paragraph_section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph=paragraph,
            title="Paragraf",
            sort_order=sort_order,
        )
        return legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph_section.id,
            section_number=section_number,
            text=f"Text § {paragraph} odst. {section_number}",
            sort_order=sort_order + 1,
        )

    def test_list_source_section_ids_for_requirement_falls_back_to_legacy_column(self) -> None:
        document = self._create_document(
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        section = self._create_subsection(document, version)

        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        requirement = LegalRequirement(
            regulation_name="Legacy požadavek",
            source_section_id=section.id,
            legal_section_id=section.id,
            legal_document_id=document.id,
            active=True,
        )
        requirement = legal_requirement_service.repository.add(requirement)

        section_ids = legal_requirement_service.list_source_section_ids_for_requirement(requirement.id)
        self.assertEqual(section_ids, [section.id])

    def test_create_requirement_with_multiple_sources(self) -> None:
        zp = self._create_document(
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        zp_version = legal_document_version_service.create(
            legal_document_id=zp.id,
            version_name="ZP verze",
        )
        zp_section = self._create_subsection(zp, zp_version, paragraph="104", section_number="1")

        nv = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="Nařízení vlády",
            number="390/2021 Sb.",
            year=2021,
            short_title="NV",
        )
        nv_version = legal_document_version_service.create(
            legal_document_id=nv.id,
            version_name="NV verze",
        )
        nv_section = self._create_subsection(nv, nv_version, paragraph="5", section_number="2")

        requirement = legal_requirement_service.create_requirement(
            regulation_name="OOPP",
            legal_document_id=zp.id,
            legal_section_id=zp_section.id,
            source_section_ids=[zp_section.id, nv_section.id],
            requirement_summary="Zajistit OOPP",
            processing_status=PROCESSING_NEW,
        )

        self.assertEqual(requirement.source_section_id, zp_section.id)
        section_ids = legal_requirement_service.list_source_section_ids_for_requirement(requirement.id)
        self.assertEqual(section_ids, [zp_section.id, nv_section.id])

        self.assertIsNotNone(legal_requirement_service.get_by_source_section_id(zp_section.id))
        self.assertIsNotNone(legal_requirement_service.get_by_source_section_id(nv_section.id))
        self.assertEqual(
            legal_requirement_service.get_by_source_section_id(nv_section.id).id,
            requirement.id,
        )

    def test_update_requirement_replaces_sources(self) -> None:
        document = self._create_document(
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        first = self._create_subsection(document, version, paragraph="101", section_number="1", sort_order=1)
        second = self._create_subsection(document, version, paragraph="102", section_number="1", sort_order=3)

        requirement = legal_requirement_service.create_requirement(
            regulation_name="Požadavek",
            legal_document_id=document.id,
            legal_section_id=first.id,
            source_section_ids=[first.id],
            requirement_summary="Text",
        )
        updated = legal_requirement_service.update_requirement(
            requirement.id,
            regulation_name="Požadavek",
            legal_document_id=document.id,
            legal_section_id=first.id,
            source_section_ids=[first.id, second.id],
            requirement_summary="Text",
        )
        assert updated is not None
        section_ids = legal_requirement_service.list_source_section_ids_for_requirement(requirement.id)
        self.assertEqual(section_ids, [first.id, second.id])

    def test_get_source_section_requirement_statuses_uses_junction(self) -> None:
        document = self._create_document(
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        first = self._create_subsection(document, version, paragraph="101", section_number="1", sort_order=1)
        second = self._create_subsection(document, version, paragraph="102", section_number="1", sort_order=3)

        legal_requirement_service.create_requirement(
            regulation_name="Procesní požadavek",
            legal_document_id=document.id,
            legal_section_id=first.id,
            source_section_ids=[first.id, second.id],
            requirement_summary="Text",
            processing_status=PROCESSING_APPROVED,
        )

        statuses = legal_requirement_service.get_source_section_requirement_statuses(
            [first.id, second.id],
        )
        self.assertEqual(statuses[first.id], REQUIREMENT_STATUS_APPROVED)
        self.assertEqual(statuses[second.id], REQUIREMENT_STATUS_APPROVED)

    def test_json_import_creates_all_source_links(self) -> None:
        zp = self._create_document(
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )
        zp_version = legal_document_version_service.create(
            legal_document_id=zp.id,
            version_name="ZP verze",
        )
        zp_paragraph = legal_section_service.create(
            legal_document_id=zp.id,
            legal_document_version_id=zp_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="104",
            title="OOPP",
            sort_order=1,
        )
        zp_section = legal_section_service.create(
            legal_document_id=zp.id,
            legal_document_version_id=zp_version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=zp_paragraph.id,
            section_number="1",
            text="ZP text",
            sort_order=2,
        )

        nv = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="Nařízení vlády",
            number="390",
            year=2021,
            short_title="NV",
        )
        nv_version = legal_document_version_service.create(
            legal_document_id=nv.id,
            version_name="NV verze",
        )
        nv_paragraph = legal_section_service.create(
            legal_document_id=nv.id,
            legal_document_version_id=nv_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            title="OOPP NV",
            sort_order=1,
        )
        nv_section = legal_section_service.create(
            legal_document_id=nv.id,
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
                    "document_number": "262",
                    "document_year": 2006,
                    "provision_label": "§ 104 odst. 1",
                    "title": "OOPP",
                    "fulfillment_text": "Zajistit OOPP",
                    "sources": [
                        {
                            "document_number": "262",
                            "document_year": 2006,
                            "provision_label": "§ 104 odst. 1",
                        },
                        {
                            "document_number": "390",
                            "document_year": 2021,
                            "provision_label": "§ 5 odst. 2",
                        },
                    ],
                },
            ]),
        )

        self.assertEqual(summary.ok_count, 1)
        saved = legal_requirement_service.get_by_source_section_id(zp_section.id)
        assert saved is not None
        section_ids = legal_requirement_service.list_source_section_ids_for_requirement(saved.id)
        self.assertEqual(section_ids, [zp_section.id, nv_section.id])

    def test_json_import_skips_when_any_source_already_linked(self) -> None:
        document = self._create_document(
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Test",
            sort_order=1,
        )
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Text",
            sort_order=2,
        )

        legal_requirement_service.create_requirement(
            regulation_name="Existující",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_ids=[section.id],
            requirement_summary="Text",
            processing_status=PROCESSING_NEW,
        )

        summary = legal_requirement_json_import_service.import_items(
            parse_import_items([
                {
                    "document_number": "262",
                    "document_year": 2006,
                    "provision_label": "§ 101 odst. 1",
                    "title": "Nový",
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

        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.rows[0].error, DUPLICATE_SKIP_MESSAGE)

    def test_legacy_json_format_still_supported(self) -> None:
        document = self._create_document(
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Test",
            sort_order=1,
        )
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Text",
            sort_order=2,
        )

        items = parse_import_items([
            {
                "document_number": "262",
                "document_year": 2006,
                "provision_label": "§ 101 odst. 1",
                "title": "Legacy",
            },
        ])
        self.assertEqual(len(items[0].sources), 1)

        summary = legal_requirement_json_import_service.import_items(items)
        self.assertEqual(summary.rows[0].status, REQUIREMENT_IMPORT_STATUS_OK)
        saved = legal_requirement_service.get_by_source_section_id(section.id)
        assert saved is not None
        self.assertEqual(
            legal_requirement_service.list_source_section_ids_for_requirement(saved.id),
            [section.id],
        )


if __name__ == "__main__":
    unittest.main()
