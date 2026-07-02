import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QLabel

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)


_STORAGE_BOOTSTRAPPED = False


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
    global validate_knowledge_file
    global AudityKnowledgeEditorDialog
    global AudityKnowledgeSectionEditorWidget
    global KNOWLEDGE_EDITOR_SECTION_TABS
    global KNOWLEDGE_EDITOR_TAB_PLACEHOLDER

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.constants import (
        KNOWLEDGE_EDITOR_SECTION_TABS,
        KNOWLEDGE_EDITOR_TAB_PLACEHOLDER,
    )
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import validate_knowledge_file
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
    from moduly.audity.ui.audity_knowledge_section_editor_widget import (
        AudityKnowledgeSectionEditorWidget,
    )


_bootstrap_storage()
_import_services()


_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"


class AudityKnowledgeSectionEditorServiceTestCase(unittest.TestCase):
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
        self._path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        bundled = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _knowledge_file_path(self) -> Path:
        process = audit_knowledge_service.get_process_by_id(_PROCESS_ID, ensure=False)
        assert process is not None and process.soubor_znalosti
        return audit_knowledge_service.audity_dir / process.soubor_znalosti

    def _section_from_file(self) -> dict:
        with self._knowledge_file_path().open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return next(
            item for item in payload.get("sekce") or [] if item.get("id") == _SECTION_ID
        )

    def _save_metadata(self, **changes) -> list[str]:
        section = self._section_from_file()
        metadata = {
            "nazev": changes.get("nazev", section.get("nazev")),
            "popis": changes.get("popis", section.get("popis")),
            "cil_overeni": changes.get("cil_overeni", section.get("cil_overeni")),
            "poradi": changes.get("poradi", section.get("poradi")),
            "aktivni": changes.get("aktivni", section.get("aktivni", True)),
        }
        return audit_knowledge_editor_service.save_section_metadata(
            _PROCESS_ID,
            _SECTION_ID,
            metadata,
        )

    def test_save_section_metadata_changes_nazev(self) -> None:
        errors = self._save_metadata(nazev="Editor test — název oblasti")
        self.assertEqual(errors, [], msg="; ".join(errors))

        section = self._section_from_file()
        self.assertEqual(section["nazev"], "Editor test — název oblasti")

    def test_save_section_metadata_changes_popis(self) -> None:
        errors = self._save_metadata(popis="Editor test — popis oblasti.")
        self.assertEqual(errors, [])

        section = self._section_from_file()
        self.assertEqual(section["popis"], "Editor test — popis oblasti.")

    def test_save_section_metadata_changes_cil_overeni(self) -> None:
        errors = self._save_metadata(cil_overeni="Editor test — cíl ověření.")
        self.assertEqual(errors, [])

        section = self._section_from_file()
        self.assertEqual(section["cil_overeni"], "Editor test — cíl ověření.")

    def test_save_section_metadata_changes_poradi(self) -> None:
        errors = self._save_metadata(poradi=999)
        self.assertEqual(errors, [])

        section = self._section_from_file()
        self.assertEqual(section["poradi"], 999)

    def test_save_section_metadata_changes_aktivni(self) -> None:
        errors = self._save_metadata(aktivni=False)
        self.assertEqual(errors, [])

        section = self._section_from_file()
        self.assertFalse(section["aktivni"])

    def test_save_section_metadata_creates_backup(self) -> None:
        errors = self._save_metadata(nazev="Editor test — záloha")
        self.assertEqual(errors, [], msg="; ".join(errors))

        backup_dir = audit_knowledge_editor_service.backup_dir()
        backups = list(backup_dir.glob("urazy_mimo_udalosti.json.*.bak"))
        self.assertGreaterEqual(len(backups), 1)

    def test_save_section_metadata_refreshes_tree_label(self) -> None:
        editor_path = audit_knowledge_editor_service.resolve_user_path(
            "audity/urazy_mimo_udalosti.json"
        )
        self.assertEqual(editor_path.resolve(), self._knowledge_file_path().resolve())

        errors = self._save_metadata(nazev="Editor test — refresh stromu")
        self.assertEqual(errors, [], msg="; ".join(errors))

        section = self._section_from_file()
        self.assertEqual(section["nazev"], "Editor test — refresh stromu")

        process = audit_knowledge_service.get_process_by_id(_PROCESS_ID, ensure=False)
        assert process is not None
        knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
        assert knowledge is not None
        loaded_section = next(
            item for item in knowledge.get("sekce") or [] if item.get("id") == _SECTION_ID
        )
        self.assertEqual(loaded_section["nazev"], "Editor test — refresh stromu")

        reloaded_roots = audit_knowledge_service.get_knowledge_tree(
            include_inactive=True,
            ensure=False,
        )
        process_node = next(
            root for root in reloaded_roots if root.process_id == _PROCESS_ID
        )
        section_node = next(
            node for node in process_node.children if node.node_id == _SECTION_ID
        )
        self.assertEqual(section_node.label, "Editor test — refresh stromu")

    def test_save_section_metadata_keeps_valid_json(self) -> None:
        errors = self._save_metadata(nazev="Editor test — validace JSON")
        self.assertEqual(errors, [])

        validation_errors = validate_knowledge_file(self._path)
        self.assertEqual(validation_errors, [])


class AudityKnowledgeSectionEditorWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        _bootstrap_storage()
        _import_services()
        cls._app = QApplication.instance() or QApplication([])

    def test_section_editor_has_metadata_fields_and_read_only_tabs(self) -> None:
        from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_LIST_TABS

        widget = AudityKnowledgeSectionEditorWidget()

        self.assertEqual(
            widget._tabs.count(),
            1 + len(KNOWLEDGE_EDITOR_SECTION_LIST_TABS) + 2,
        )
        self.assertEqual(widget._tabs.tabText(0), "Auditní tvrzení")
        self.assertIs(widget._tabs.widget(0), widget._assertions_widget)
        self.assertEqual(len(widget._list_widgets), len(KNOWLEDGE_EDITOR_SECTION_LIST_TABS))
        self.assertEqual(widget._tabs.tabText(9), "Postup kontroly")
        self.assertEqual(widget._tabs.tabText(10), "Referenční fotografie")


class AudityKnowledgeEditorDialogSectionTestCase(unittest.TestCase):
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
        self._path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        bundled = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _select_section(self, dialog: AudityKnowledgeEditorDialog) -> None:
        self.assertTrue(
            dialog.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID)
        )

    def test_dialog_section_selection_shows_editor(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self._select_section(dialog)

        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_SECTION)
        self.assertTrue(dialog._apply_btn.isEnabled())
        self.assertEqual(dialog.section_editor.section_id, _SECTION_ID)


if __name__ == "__main__":
    unittest.main()
