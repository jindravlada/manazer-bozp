import importlib
import json
import shutil
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

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_usage_service import (
        legal_requirement_usage_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

_RIZENI_RIZIK_PROCESS_ID = "rizeni_rizik"
_LINKED_SECTION_ID = "identifikace_nebezpeci"


class LegalRequirementUsageServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        audit_knowledge_editor_service.ensure_user_catalogs()
        self._knowledge_path = audit_knowledge_service.audity_dir / "rizeni_rizik.json"
        bundled = editable_catalog_service.bundled_path("audity/rizeni_rizik.json")
        shutil.copy2(bundled, self._knowledge_path)
        with self._knowledge_path.open(encoding="utf-8") as handle:
            self._original_knowledge = json.load(handle)

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def tearDown(self) -> None:
        self._knowledge_path.write_text(
            json.dumps(self._original_knowledge, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _create_document_with_subsections(self):
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
        paragraph_101 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="§ 101",
            sort_order=1,
        )
        paragraph_102 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="102",
            title="§ 102",
            sort_order=2,
        )
        return document, paragraph_101, paragraph_102

    def _link_audit_section(self, requirement_id: int) -> None:
        with self._knowledge_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        section = next(
            item for item in payload.get("sekce") or [] if item.get("id") == _LINKED_SECTION_ID
        )
        errors = audit_knowledge_editor_service.save_section_metadata(
            _RIZENI_RIZIK_PROCESS_ID,
            _LINKED_SECTION_ID,
            {
                "nazev": section.get("nazev"),
                "popis": section.get("popis"),
                "cil_overeni": section.get("cil_overeni"),
                "poradi": section.get("poradi"),
                "aktivni": section.get("aktivni", True),
                "legal_requirement_id": requirement_id,
            },
        )
        self.assertEqual(errors, [], msg="; ".join(errors))

    def test_lists_legal_provisions_from_sources(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        _, paragraph_101, paragraph_102 = self._create_document_with_subsections()
        legal_requirement_service.attach_source_section(requirement.id, paragraph_101.id)
        legal_requirement_service.attach_source_section(requirement.id, paragraph_102.id)

        usage = legal_requirement_usage_service.get_usage(requirement.id)

        self.assertEqual(len(usage.legal_provisions), 2)
        labels = [item.label for item in usage.legal_provisions]
        self.assertIn("262/2006 Sb. § 101", labels)
        self.assertIn("262/2006 Sb. § 102", labels)
        self.assertEqual(usage.audit_areas, ())
        self.assertEqual(usage.audit_assertions, ())
        self.assertEqual(usage.inspection_areas, ())
        self.assertEqual(usage.inspection_questions, ())

    def test_lists_audit_areas_and_assertions_linked_by_legal_requirement_id(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        self._link_audit_section(requirement.id)

        usage = legal_requirement_usage_service.get_usage(requirement.id)

        self.assertEqual(usage.legal_provisions, ())
        self.assertEqual(len(usage.audit_areas), 1)
        self.assertIn("Řízení rizik", usage.audit_areas[0].display_label)
        self.assertIn("Identifikace", usage.audit_areas[0].display_label)
        self.assertGreater(len(usage.audit_assertions), 0)
        self.assertTrue(all(item.text for item in usage.audit_assertions))

    def test_returns_empty_usage_when_nothing_is_linked(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Samostatný proces",
            process_code="P-099",
        )

        usage = legal_requirement_usage_service.get_usage(requirement.id)

        self.assertEqual(usage.legal_provisions, ())
        self.assertEqual(usage.audit_areas, ())
        self.assertEqual(usage.audit_assertions, ())
        self.assertEqual(usage.inspection_areas, ())
        self.assertEqual(usage.inspection_questions, ())
        self.assertEqual(usage.warnings, ())


class LegalRequirementProverkyUsageTestCase(unittest.TestCase):
    """Fáze 97d – automatické použití procesu v metodikách prověrek."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service

        import core.services.editable_catalog_service as editable_catalog_module
        import moduly.proverky.sluzby.proverky_knowledge_service as proverky_module

        importlib.reload(editable_catalog_module)
        importlib.reload(proverky_module)

        self._proverky = proverky_module.proverky_knowledge_service
        self._proverky.ensure_catalogs()

        area = self._proverky.get_area_by_id("prvni_pomoc")
        self.assertIsNotNone(area)
        self._area_id = area.id
        self._path = self._proverky.proverky_dir / area.soubor_znalosti
        bundled = editable_catalog_service.bundled_path(f"proverky/{area.soubor_znalosti}")
        shutil.copy2(bundled, self._path)
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

        sections = self._proverky.list_sections(self._area_id, include_inactive=True)
        self.assertGreaterEqual(len(sections), 1)
        self._section_id = str(sections[0].get("id") or "")
        self._second_section_id = None
        for section in sections[1:]:
            section_id = str(section.get("id") or "").strip()
            if section_id:
                self._second_section_id = section_id
                break

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _link_section(self, section_id: str, requirement_id: int) -> None:
        section = self._proverky.get_section(self._area_id, section_id)
        self.assertIsNotNone(section)
        payload = dict(section)
        payload["legal_requirement_id"] = requirement_id
        ok, errors = self._proverky.save_section(self._area_id, section_id, payload)
        self.assertTrue(ok, msg="; ".join(errors))

    def test_linked_inspection_section_and_questions_are_listed(self) -> None:
        self._link_section(self._section_id, self._requirement.id)

        usage = legal_requirement_usage_service.get_usage(self._requirement.id)

        self.assertEqual(len(usage.inspection_areas), 1)
        self.assertIn("Prověrky BOZP", usage.inspection_areas[0].display_label)
        self.assertIn(
            usage.inspection_areas[0].section_name,
            usage.inspection_areas[0].display_label,
        )
        self.assertGreater(len(usage.inspection_questions), 0)
        self.assertTrue(all(item.text for item in usage.inspection_questions))

    def test_unlinked_section_is_not_listed(self) -> None:
        usage = legal_requirement_usage_service.get_usage(self._requirement.id)
        self.assertEqual(usage.inspection_areas, ())
        self.assertEqual(usage.inspection_questions, ())

    def test_multiple_sections_can_share_one_process(self) -> None:
        self._link_section(self._section_id, self._requirement.id)
        if self._second_section_id:
            self._link_section(self._second_section_id, self._requirement.id)

        usage = legal_requirement_usage_service.get_usage(self._requirement.id)
        self.assertGreaterEqual(len(usage.inspection_areas), 1)
        if self._second_section_id:
            self.assertEqual(len(usage.inspection_areas), 2)

    def test_older_json_without_legal_requirement_id_works(self) -> None:
        section = self._proverky.get_section(self._area_id, self._section_id)
        self.assertIsNotNone(section)
        self.assertNotIn("legal_requirement_id", section)

        usage = legal_requirement_usage_service.get_usage(self._requirement.id)
        self.assertEqual(usage.inspection_areas, ())
        self.assertEqual(usage.inspection_questions, ())
        self.assertEqual(usage.warnings, ())

    def test_corrupted_proverky_json_does_not_break_usage(self) -> None:
        self._link_section(self._section_id, self._requirement.id)
        self._path.write_text("{ not-valid-json", encoding="utf-8")

        usage = legal_requirement_usage_service.get_usage(self._requirement.id)

        self.assertEqual(usage.inspection_areas, ())
        self.assertEqual(usage.inspection_questions, ())
        self.assertTrue(usage.warnings)
        self.assertTrue(any("nelze načíst" in item for item in usage.warnings))
        # Ostatní části (prázdné auditní vazby) zůstávají dostupné.
        self.assertEqual(usage.audit_areas, ())

    def test_empty_state_shows_zadne_in_widget(self) -> None:
        from PySide6.QtWidgets import QLabel

        from moduly.pravni_pozadavky.ui.legal_requirement_automatic_usage_widget import (
            LegalRequirementAutomaticUsageWidget,
        )

        widget = LegalRequirementAutomaticUsageWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Oblasti prověrek", labels)
        self.assertIn("Kontrolní otázky prověrek", labels)
        self.assertGreaterEqual(labels.count("žádné"), 2)


if __name__ == "__main__":
    unittest.main()
