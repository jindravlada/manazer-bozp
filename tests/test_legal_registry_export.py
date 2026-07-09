import importlib
import json
import tempfile
import unittest
from datetime import date, datetime
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
        PROCESSING_APPROVED,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.import_export.legal_registry_export_service import (
        APPLICATION_NAME,
        EXPORT_VERSION,
        legal_registry_export_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRegistryExportServiceTestCase(unittest.TestCase):
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
            "title": "Školení BOZP",
            "process_code": "P-001",
            "regulation_name": "Zákoník práce",
            "regulation_number": "262/2006 Sb.",
            "provision": "§ 103",
            "area": "BOZP",
            "requirement_summary": "Zajistit bezpečnost práce",
            "organization_impact": "Nutné školení zaměstnanců",
            "processing_status": PROCESSING_APPROVED,
        }
        defaults.update(kwargs)
        return legal_requirement_service.create_requirement(**defaults)

    def test_build_data_contains_expected_structure(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        parent = self._create_requirement(
            title="Rodičovský proces",
            process_code="P-001",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
        )
        child = self._create_requirement(
            title="Podřízený proces",
            process_code="P-001.1",
            parent_requirement_id=parent.id,
        )
        legal_requirement_service.attach_source_section(parent.id, section.id)

        created_at = datetime(2026, 7, 9, 12, 36, 0)
        data = legal_registry_export_service.build_data(created_at=created_at)

        self.assertEqual(data["export_version"], EXPORT_VERSION)
        self.assertEqual(data["created_at"], created_at.isoformat())
        self.assertEqual(data["application"], APPLICATION_NAME)
        self.assertEqual(len(data["requirements"]), 2)
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(len(data["documents"]), 1)
        self.assertEqual(len(data["versions"]), 1)
        self.assertEqual(len(data["sections"]), 1)

        exported_parent = next(item for item in data["requirements"] if item["id"] == parent.id)
        exported_child = next(item for item in data["requirements"] if item["id"] == child.id)
        self.assertIsNone(exported_parent["parent_requirement_id"])
        self.assertEqual(exported_child["parent_requirement_id"], parent.id)
        self.assertEqual(exported_parent["process_code"], "P-001")
        self.assertTrue(exported_parent["active"])

        exported_source = data["sources"][0]
        self.assertEqual(exported_source["requirement_id"], parent.id)
        self.assertEqual(exported_source["legal_section_id"], section.id)
        self.assertEqual(exported_source["sort_order"], 1)

        exported_section = data["sections"][0]
        self.assertEqual(exported_section["id"], section.id)
        self.assertEqual(exported_section["legal_document_id"], document.id)
        self.assertEqual(exported_section["legal_document_version_id"], version.id)
        self.assertEqual(exported_section["sort_order"], 10)

    def test_build_data_exports_only_active_records(self) -> None:
        active_document = self._create_document(title="Aktivní předpis")
        inactive_document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Archivní předpis",
            number="1/2000 Sb.",
            year=2000,
            short_title="Archiv",
        )
        legal_document_service.deactivate(inactive_document.id)

        active_version = self._create_version(active_document)
        inactive_version = legal_document_version_service.create(
            legal_document_id=active_document.id,
            version_name="Archivní verze",
        )
        legal_document_version_service.deactivate(inactive_version.id)

        active_section = self._create_section(active_document, active_version)
        inactive_section = legal_section_service.create(
            legal_document_id=active_document.id,
            legal_document_version_id=active_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="999",
            title="Archivní ustanovení",
            text="Text.",
            sort_order=99,
        )
        legal_section_service.deactivate(inactive_section.id)

        active_requirement = self._create_requirement(process_code="P-010")
        inactive_requirement = self._create_requirement(
            title="Archivní proces",
            process_code="P-020",
        )
        legal_requirement_service.archive_requirement(inactive_requirement.id)
        legal_requirement_service.attach_source_section(active_requirement.id, active_section.id)

        data = legal_registry_export_service.build_data()

        self.assertEqual(
            {item["id"] for item in data["requirements"]},
            {active_requirement.id},
        )
        self.assertEqual(
            {item["id"] for item in data["documents"]},
            {active_document.id},
        )
        self.assertEqual(
            {item["id"] for item in data["versions"]},
            {active_version.id},
        )
        self.assertEqual(
            {item["id"] for item in data["sections"]},
            {active_section.id},
        )
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(data["sources"][0]["requirement_id"], active_requirement.id)

    def test_export_to_file_writes_valid_json(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        requirement = self._create_requirement(
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
        )
        legal_requirement_service.attach_source_section(requirement.id, section.id)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / legal_registry_export_service.build_default_filename(
                created_at=datetime(2026, 7, 9, 15, 30, 45),
            )
            result = legal_registry_export_service.export_to_file(file_path)

            self.assertEqual(result.file_path, file_path)
            self.assertEqual(result.requirement_count, 1)
            self.assertEqual(result.source_count, 1)
            self.assertEqual(result.document_count, 1)
            self.assertEqual(result.version_count, 1)
            self.assertEqual(result.section_count, 1)
            self.assertEqual(file_path.name, "legal_registry_export_20260709_153045.json")

            loaded = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["export_version"], EXPORT_VERSION)
            self.assertEqual(loaded["requirements"][0]["id"], requirement.id)
            self.assertEqual(loaded["sources"][0]["legal_section_id"], section.id)

    def test_build_default_filename_uses_timestamp(self) -> None:
        filename = legal_registry_export_service.build_default_filename(
            created_at=datetime(2026, 7, 9, 8, 5, 3),
        )
        self.assertEqual(filename, "legal_registry_export_20260709_080503.json")


if __name__ == "__main__":
    unittest.main()
