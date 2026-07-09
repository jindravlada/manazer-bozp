import copy
import importlib
import json
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
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
    from moduly.pravni_pozadavky.import_export.legal_registry_export_service import (
        APPLICATION_NAME,
        EXPORT_VERSION,
        legal_registry_export_service,
    )
    from moduly.pravni_pozadavky.import_export.legal_registry_import_service import (
        legal_registry_import_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_sanction_service import (
        legal_requirement_sanction_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.ukoly.sluzby.task_service import task_service


class LegalRegistryBackupRestoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._clear_registry_tables()
        self._clear_tasks()

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

    def _clear_tasks(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.commit()

    def _create_document(self, *, title: str = "Zákoník práce", active: bool = True):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        if not active:
            legal_document_service.deactivate(document.id)
            document = legal_document_service.get_by_id(document.id)
        return document

    def _create_version(self, document, *, version_name: str = "Verze 2024", active: bool = True):
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name=version_name,
        )
        if not active:
            legal_document_version_service.deactivate(version.id)
            version = legal_document_version_service.get_by_id(version.id)
        return version

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
        section = legal_section_service.create(**defaults)
        if defaults.get("active") is False:
            legal_section_service.deactivate(section.id)
            section = legal_section_service.get_by_id(section.id)
        return section

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

    def _build_registry_fixture(self):
        active_document = self._create_document(title="Aktivní předpis")
        inactive_document = self._create_document(title="Archivní předpis", active=False)
        active_version = self._create_version(active_document)
        inactive_version = self._create_version(
            active_document,
            version_name="Archivní verze",
            active=False,
        )
        active_section = self._create_section(active_document, active_version)
        inactive_section = self._create_section(
            active_document,
            active_version,
            paragraph="999",
            title="Archivní ustanovení",
            text="Text.",
            sort_order=99,
            active=False,
        )

        parent = self._create_requirement(
            title="Rodičovský proces",
            process_code="P-001",
            legal_document_id=active_document.id,
            legal_section_id=active_section.id,
            source_section_id=active_section.id,
        )
        child = self._create_requirement(
            title="Podřízený proces",
            process_code="P-001.1",
            parent_requirement_id=parent.id,
        )
        archived = self._create_requirement(
            title="Archivní proces",
            process_code="P-020",
        )
        legal_requirement_service.archive_requirement(archived.id)
        merged_source = self._create_requirement(
            title="Sloučený proces",
            process_code="P-030",
        )
        merged_source = legal_requirement_service.repository.get_by_id(merged_source.id)
        merged_source.merged_into_requirement_id = parent.id
        legal_requirement_service.repository.update(merged_source)

        legal_requirement_service.attach_source_section(parent.id, active_section.id)
        sanction = legal_requirement_sanction_service.create(
            requirement_id=parent.id,
            authority="OIP",
            description="Pokuta za porušení povinnosti",
            max_amount=Decimal("500000.00"),
            active=False,
        )
        run = legal_check_run_service.create(
            title="Kontrola 1/2026",
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
            active=False,
        )
        change = legal_change_service.create(
            legal_document_id=active_document.id,
            legal_document_version_id=active_version.id,
            legal_section_id=active_section.id,
            legal_check_run_id=run.id,
            change_type=CHANGE_NOVELIZATION,
            title="Novelizace zákona",
            evaluated=False,
            active=True,
        )
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.repository.legal_change_section_repository import (
            LegalChangeSectionRepository,
        )

        change_section = LegalChangeSectionRepository().create(
            LegalChangeSection(
                legal_change_id=change.id,
                section_key="§:103",
                section_label="§ 103",
                change_type=CHANGE_SECTION_MODIFIED,
                note="Změněno znění",
            ),
        )

        return {
            "active_document": active_document,
            "inactive_document": inactive_document,
            "active_version": active_version,
            "inactive_version": inactive_version,
            "active_section": active_section,
            "inactive_section": inactive_section,
            "parent": parent,
            "child": child,
            "archived": archived,
            "merged_source": merged_source,
            "sanction": sanction,
            "run": run,
            "change": change,
            "change_section": change_section,
        }

    def _strip_created_at(self, payload: dict) -> dict:
        normalized = copy.deepcopy(payload)
        normalized.pop("created_at", None)
        return normalized

    def test_build_data_contains_record_counts(self) -> None:
        self._build_registry_fixture()
        data = legal_registry_export_service.build_data(created_at=datetime(2026, 7, 9, 12, 36, 0))

        self.assertEqual(data["export_version"], EXPORT_VERSION)
        self.assertEqual(data["application"], APPLICATION_NAME)
        self.assertEqual(
            data["record_counts"],
            {
                "documents": 2,
                "versions": 2,
                "sections": 2,
                "requirements": 4,
                "sources": 1,
                "sanctions": 1,
                "check_runs": 1,
                "changes": 1,
                "change_sections": 1,
            },
        )

    def test_build_data_exports_inactive_records(self) -> None:
        fixture = self._build_registry_fixture()
        data = legal_registry_export_service.build_data()

        self.assertIn(fixture["inactive_document"].id, {item["id"] for item in data["documents"]})
        self.assertIn(fixture["inactive_version"].id, {item["id"] for item in data["versions"]})
        self.assertIn(fixture["inactive_section"].id, {item["id"] for item in data["sections"]})
        self.assertIn(fixture["archived"].id, {item["id"] for item in data["requirements"]})
        self.assertFalse(
            next(item for item in data["documents"] if item["id"] == fixture["inactive_document"].id)[
                "active"
            ],
        )

        merged = next(
            item for item in data["requirements"] if item["id"] == fixture["merged_source"].id
        )
        self.assertEqual(merged["merged_into_requirement_id"], fixture["parent"].id)

    def test_import_restores_all_registry_tables_with_ids(self) -> None:
        fixture = self._build_registry_fixture()
        outside_task = task_service.create_task(
            title="Úkol mimo registr",
            description="Nesmí zmizet",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "registry_backup.json"
            legal_registry_export_service.export_to_file(file_path)

            self._clear_registry_tables()
            self._create_requirement(title="Jiný proces", process_code="P-999")

            result = legal_registry_import_service.import_from_file(file_path)

            self.assertEqual(result.document_count, 2)
            self.assertEqual(result.version_count, 2)
            self.assertEqual(result.section_count, 2)
            self.assertEqual(result.requirement_count, 4)
            self.assertEqual(result.source_count, 1)
            self.assertEqual(result.sanction_count, 1)
            self.assertEqual(result.check_run_count, 1)
            self.assertEqual(result.change_count, 1)
            self.assertEqual(result.change_section_count, 1)

            restored_parent = legal_requirement_service.get_by_id(fixture["parent"].id)
            restored_child = legal_requirement_service.get_by_id(fixture["child"].id)
            restored_change = legal_change_service.get_by_id(fixture["change"].id)
            restored_task = task_service.get_task_by_id(outside_task.id)

            self.assertIsNotNone(restored_parent)
            self.assertIsNotNone(restored_child)
            self.assertEqual(restored_child.parent_requirement_id, fixture["parent"].id)
            self.assertIsNotNone(restored_change)
            self.assertEqual(restored_change.legal_check_run_id, fixture["run"].id)
            self.assertIsNotNone(restored_task)
            self.assertEqual(restored_task.title, "Úkol mimo registr")

    def test_export_import_export_roundtrip_is_equivalent_except_created_at(self) -> None:
        self._build_registry_fixture()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "registry_backup.json"
            legal_registry_export_service.export_to_file(file_path)
            first_export = legal_registry_export_service.build_data(
                created_at=datetime(2026, 7, 9, 10, 0, 0),
            )

            self._clear_registry_tables()
            legal_registry_import_service.import_from_file(file_path)
            second_export = legal_registry_export_service.build_data(
                created_at=datetime(2026, 7, 9, 11, 0, 0),
            )

        self.assertEqual(
            self._strip_created_at(first_export),
            self._strip_created_at(second_export),
        )

    def test_export_to_file_writes_valid_json(self) -> None:
        self._build_registry_fixture()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / legal_registry_export_service.build_default_filename(
                created_at=datetime(2026, 7, 9, 15, 30, 45),
            )
            result = legal_registry_export_service.export_to_file(file_path)

            self.assertEqual(result.document_count, 2)
            self.assertEqual(result.requirement_count, 4)
            self.assertEqual(file_path.name, "legal_registry_export_20260709_153045.json")

            loaded = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["export_version"], EXPORT_VERSION)
            self.assertIn("record_counts", loaded)
            self.assertEqual(loaded["record_counts"]["changes"], 1)

    def test_build_default_filename_uses_timestamp(self) -> None:
        filename = legal_registry_export_service.build_default_filename(
            created_at=datetime(2026, 7, 9, 8, 5, 3),
        )
        self.assertEqual(filename, "legal_registry_export_20260709_080503.json")


if __name__ == "__main__":
    unittest.main()
