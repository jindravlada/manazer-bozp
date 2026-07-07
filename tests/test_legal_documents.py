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
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_export_context_service import (
        legal_document_export_context_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalDocumentServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
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

    def test_create_legal_document(self) -> None:
        document = self._create_document()

        self.assertIsNotNone(document.id)
        self.assertEqual(document.title, "Zákoník práce")
        self.assertTrue(document.active)

    def test_update_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Původní název",
        )
        updated = legal_document_service.update(
            document.id,
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Upravený název",
            number="123/2020 Sb.",
            year=2020,
            short_title="Test",
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.title, "Upravený název")
        self.assertEqual(updated.short_title, "Test")

    def test_deactivate_and_restore_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="K deaktivaci",
        )

        deactivated = legal_document_service.deactivate(document.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_document_service.list_all()
        self.assertEqual(active_only, [])

        restored = legal_document_service.restore(document.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_create_version_for_document(self) -> None:
        document = self._create_document()
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Účinnost od 1.1.2024",
            effective_from=date(2024, 1, 1),
            publication_date=date(2023, 12, 15),
            source_url="https://example.com/zp",
            checksum="abc123",
        )

        self.assertIsNotNone(version.id)
        self.assertEqual(version.legal_document_id, document.id)
        self.assertEqual(version.version_name, "Účinnost od 1.1.2024")
        self.assertTrue(version.active)
        self.assertEqual(version.checksum, "abc123")

    def test_update_version(self) -> None:
        document = self._create_document()
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Původní verze",
        )
        updated = legal_document_version_service.update(
            version.id,
            legal_document_id=document.id,
            version_name="Upravená verze",
            effective_from=date(2025, 6, 1),
            effective_to=date(2025, 12, 31),
            note="Poznámka k verzi",
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.version_name, "Upravená verze")
        self.assertEqual(updated.effective_from, date(2025, 6, 1))
        self.assertEqual(updated.note, "Poznámka k verzi")

    def test_deactivate_and_restore_version(self) -> None:
        document = self._create_document()
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="K deaktivaci",
        )

        deactivated = legal_document_version_service.deactivate(version.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_document_version_service.list_by_document(document.id)
        self.assertEqual(active_only, [])

        restored = legal_document_version_service.restore(version.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_document_can_have_multiple_versions(self) -> None:
        document = self._create_document()
        first = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 1",
        )
        second = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2",
        )

        versions = legal_document_version_service.list_by_document(document.id)
        self.assertEqual(len(versions), 2)
        self.assertEqual({item.id for item in versions}, {first.id, second.id})

    def test_export_context_includes_versions(self) -> None:
        document = self._create_document()
        legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Exportovaná verze",
            valid_from=date(2020, 1, 1),
            effective_from=date(2020, 1, 1),
            publication_date=date(2019, 12, 1),
            source_url="https://example.com/export",
            local_file_path="/data/zp.pdf",
        )

        context = legal_document_export_context_service.build_for_document(document.id)
        assert context is not None
        self.assertEqual(len(context.rows), 1)
        row = context.rows[0]
        self.assertEqual(len(row.versions), 1)
        version_row = row.versions[0]
        self.assertEqual(version_row.version_name, "Exportovaná verze")
        self.assertEqual(version_row.valid_from, "01.01.2020")
        self.assertEqual(version_row.effective_from, "01.01.2020")
        self.assertEqual(version_row.publication_date, "01.12.2019")
        self.assertEqual(version_row.source_url, "https://example.com/export")
        self.assertEqual(version_row.local_file_path, "/data/zp.pdf")
        self.assertEqual(version_row.sections, [])

    def test_create_version_requires_legal_document_id(self) -> None:
        with self.assertRaises(ValueError):
            legal_document_version_service.create(
                legal_document_id=0,
                version_name="Bez předpisu",
            )

    def test_create_version_requires_version_name(self) -> None:
        document = self._create_document()
        with self.assertRaises(ValueError):
            legal_document_version_service.create(
                legal_document_id=document.id,
                version_name="   ",
            )

    def test_create_section_for_version(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="90",
            title="Přestávka v práci",
            text="Zaměstnanci přísluší přestávka v práci.",
            sort_order=10,
        )

        self.assertIsNotNone(section.id)
        self.assertEqual(section.legal_document_id, document.id)
        self.assertEqual(section.legal_document_version_id, version.id)
        self.assertEqual(section.section_type, SECTION_PARAGRAPH)
        self.assertTrue(section.active)

    def test_update_section(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            text="Původní text",
        )
        updated = legal_section_service.update(
            section.id,
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="Upravený nadpis",
            text="Upravený text",
            sort_order=5,
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.title, "Upravený nadpis")
        self.assertEqual(updated.text, "Upravený text")
        self.assertEqual(updated.sort_order, 5)

    def test_deactivate_and_restore_section(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            text="K deaktivaci",
        )

        deactivated = legal_section_service.deactivate(section.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_section_service.list_by_version(version.id)
        self.assertEqual(active_only, [])

        restored = legal_section_service.restore(section.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_list_sections_by_document(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="3",
            text="Podle předpisu",
        )

        sections = legal_section_service.list_by_document(document.id)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].id, section.id)

    def test_list_sections_by_version(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="4",
            text="Podle verze",
        )

        sections = legal_section_service.list_by_version(version.id)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].id, section.id)

    def test_list_child_sections(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        parent = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            text="Rodič",
            sort_order=1,
        )
        child = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=parent.id,
            section_number="1",
            text="Potomek",
            sort_order=1,
        )

        children = legal_section_service.list_children(parent.id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].id, child.id)

    def test_sections_sorted_by_sort_order(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        second = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="20",
            text="Druhý",
            sort_order=20,
        )
        first = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="10",
            text="První",
            sort_order=10,
        )

        sections = legal_section_service.list_by_version(version.id)
        self.assertEqual([item.id for item in sections], [first.id, second.id])

    def test_create_section_requires_legal_document_id(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        with self.assertRaises(ValueError):
            legal_section_service.create(
                legal_document_id=0,
                legal_document_version_id=version.id,
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
            )

    def test_create_section_requires_legal_document_version_id(self) -> None:
        document = self._create_document()
        with self.assertRaises(ValueError):
            legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=0,
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
            )

    def test_create_section_requires_section_type(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        with self.assertRaises(ValueError):
            legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type="   ",
                paragraph="1",
            )

    def test_create_section_requires_content(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        with self.assertRaises(ValueError):
            legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=SECTION_PARAGRAPH,
            )

    def test_export_context_includes_sections(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="90",
            title="Přestávka",
            text="Text ustanovení",
            sort_order=15,
        )

        context = legal_document_export_context_service.build_for_document(document.id)
        assert context is not None
        version_row = context.rows[0].versions[0]
        self.assertEqual(len(version_row.sections), 1)
        section_row = version_row.sections[0]
        self.assertEqual(section_row.section_type, "Paragraf")
        self.assertEqual(section_row.paragraph, "90")
        self.assertEqual(section_row.title, "Přestávka")
        self.assertEqual(section_row.text, "Text ustanovení")
        self.assertEqual(section_row.sort_order, 15)


if __name__ == "__main__":
    unittest.main()
