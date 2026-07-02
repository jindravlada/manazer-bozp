import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)

_STORAGE_BOOTSTRAPPED = False

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_KNOWLEDGE_FILE = "urazy_mimo_udalosti.json"


def _bootstrap_storage() -> None:
    global _STORAGE_BOOTSTRAPPED
    if not _STORAGE_BOOTSTRAPPED:
        _HOME_PATCHER.start()
        _STORAGE_BOOTSTRAPPED = True

    import core.services.editable_catalog_service as editable_catalog_module
    import core.services.storage_service as storage_module
    import moduly.audity.sluzby.audit_knowledge_editor_service as editor_module
    import moduly.audity.sluzby.audit_knowledge_service as knowledge_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(editable_catalog_module)
    importlib.reload(knowledge_module)
    importlib.reload(editor_module)


def _import_services() -> None:
    global editable_catalog_service
    global audit_knowledge_editor_service
    global audit_knowledge_service
    global validate_all_catalogs
    global AudityKnowledgeSectionEditorWidget

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_TABS
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import validate_all_catalogs
    from moduly.audity.ui.audity_knowledge_section_editor_widget import (
        AudityKnowledgeSectionEditorWidget,
    )


_bootstrap_storage()
_import_services()


class _KnowledgeEditorTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        _bootstrap_storage()
        _import_services()
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _bootstrap_storage()
        _import_services()
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = audit_knowledge_service.audity_dir / _KNOWLEDGE_FILE
        bundled = editable_catalog_service.bundled_path(f"audity/{_KNOWLEDGE_FILE}")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _section_from_file(self) -> dict:
        with self._path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return next(
            item for item in payload.get("sekce") or [] if item.get("id") == _SECTION_ID
        )

    def _item_from_section(self, field_name: str, item_id: str) -> dict | None:
        section = self._section_from_file()
        for item in section.get(field_name) or []:
            if item.get("id") == item_id:
                return item
        return None


class AudityKnowledgePostupEditorServiceTestCase(_KnowledgeEditorTestBase):
    def _save_postup(self, **overrides) -> list[str]:
        payload = {
            "nazev": "Editor test — krok postupu",
            "popis": "Editor test — popis kroku.",
            "poradi": 10,
            "aktivni": True,
        }
        payload.update(overrides)
        return audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "postup_kontroly",
            payload,
        )

    def test_create_postup_step(self) -> None:
        errors = self._save_postup()
        self.assertEqual(errors, [], msg="; ".join(errors))

        created = self._item_from_section(
            "postup_kontroly",
            "editor_test_krok_postupu",
        )
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["nazev"], "Editor test — krok postupu")
        self.assertEqual(created["popis"], "Editor test — popis kroku.")

    def test_edit_postup_step(self) -> None:
        create_errors = self._save_postup()
        self.assertEqual(create_errors, [])

        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "postup_kontroly",
            {
                "nazev": "Editor test — upravený krok",
                "popis": "Editor test — upravený popis.",
                "poradi": 20,
                "aktivni": True,
            },
            item_id="editor_test_krok_postupu",
        )
        self.assertEqual(errors, [])

        updated = self._item_from_section("postup_kontroly", "editor_test_krok_postupu")
        assert updated is not None
        self.assertEqual(updated["id"], "editor_test_krok_postupu")
        self.assertEqual(updated["nazev"], "Editor test — upravený krok")

    def test_deactivate_postup_step(self) -> None:
        create_errors = self._save_postup()
        self.assertEqual(create_errors, [])

        errors = audit_knowledge_editor_service.set_section_list_item_active(
            _PROCESS_ID,
            _SECTION_ID,
            "postup_kontroly",
            "editor_test_krok_postupu",
            aktivni=False,
        )
        self.assertEqual(errors, [])

        updated = self._item_from_section("postup_kontroly", "editor_test_krok_postupu")
        assert updated is not None
        self.assertFalse(updated["aktivni"])


class AudityKnowledgeReferencePhotoEditorServiceTestCase(_KnowledgeEditorTestBase):
    def _save_photo(self, **overrides) -> list[str]:
        payload = {
            "nazev": "Editor test — referenční fotografie",
            "popis": "Editor test — popis fotografie.",
            "soubor": "/tmp/editor_test_reference.jpg",
            "poradi": 10,
            "aktivni": True,
        }
        payload.update(overrides)
        return audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "referencni_fotografie",
            payload,
        )

    def test_create_reference_photo(self) -> None:
        errors = self._save_photo()
        self.assertEqual(errors, [], msg="; ".join(errors))

        created = self._item_from_section(
            "referencni_fotografie",
            "editor_test_referencni_fotografie",
        )
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["soubor"], "/tmp/editor_test_reference.jpg")

    def test_edit_reference_photo(self) -> None:
        create_errors = self._save_photo()
        self.assertEqual(create_errors, [])

        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "referencni_fotografie",
            {
                "nazev": "Editor test — upravená fotografie",
                "popis": "Editor test — upravený popis.",
                "soubor": "/tmp/editor_test_reference_updated.jpg",
                "poradi": 20,
                "aktivni": True,
            },
            item_id="editor_test_referencni_fotografie",
        )
        self.assertEqual(errors, [])

        updated = self._item_from_section(
            "referencni_fotografie",
            "editor_test_referencni_fotografie",
        )
        assert updated is not None
        self.assertEqual(updated["id"], "editor_test_referencni_fotografie")
        self.assertEqual(updated["soubor"], "/tmp/editor_test_reference_updated.jpg")

    def test_deactivate_reference_photo(self) -> None:
        create_errors = self._save_photo()
        self.assertEqual(create_errors, [])

        errors = audit_knowledge_editor_service.set_section_list_item_active(
            _PROCESS_ID,
            _SECTION_ID,
            "referencni_fotografie",
            "editor_test_referencni_fotografie",
            aktivni=False,
        )
        self.assertEqual(errors, [])

        updated = self._item_from_section(
            "referencni_fotografie",
            "editor_test_referencni_fotografie",
        )
        assert updated is not None
        self.assertFalse(updated["aktivni"])

    def test_active_reference_photo_requires_soubor(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "referencni_fotografie",
            {
                "nazev": "Editor test — bez souboru",
                "popis": "",
                "soubor": "",
                "poradi": 10,
                "aktivni": True,
            },
        )
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("Soubor", errors[0])

    def test_create_reference_photo_creates_backup(self) -> None:
        errors = self._save_photo()
        self.assertEqual(errors, [])

        backup_dir = audit_knowledge_editor_service.backup_dir()
        backups = list(backup_dir.glob(f"{_KNOWLEDGE_FILE}.*.bak"))
        self.assertGreaterEqual(len(backups), 1)

    def test_create_reference_photo_keeps_valid_json(self) -> None:
        errors = self._save_photo()
        self.assertEqual(errors, [])

        validation_errors = validate_all_catalogs(audit_knowledge_service.audity_dir)
        self.assertEqual(validation_errors, [])


class AudityKnowledgeSectionEditorExtraTabsTestCase(_KnowledgeEditorTestBase):
    def test_section_editor_has_postup_and_reference_tabs(self) -> None:
        from moduly.audity.constants import (
            KNOWLEDGE_EDITOR_SECTION_LIST_TABS,
            KNOWLEDGE_EDITOR_SECTION_TABS,
        )

        widget = AudityKnowledgeSectionEditorWidget()
        section = self._section_from_file()
        widget.load_section(
            process_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            section=section,
        )

        self.assertEqual(widget._tabs.count(), len(KNOWLEDGE_EDITOR_SECTION_TABS))
        self.assertEqual(len(widget._list_widgets), len(KNOWLEDGE_EDITOR_SECTION_LIST_TABS))
        self.assertIs(widget._postup_widget, widget._tabs.widget(9))
        self.assertIs(widget._reference_photo_widget, widget._tabs.widget(10))


if __name__ == "__main__":
    unittest.main()
