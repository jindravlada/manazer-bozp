import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moduly.audity.sluzby.audit_knowledge_validator import SECTION_REQUIRED_FIELDS

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)

_STORAGE_BOOTSTRAPPED = False

_PROCESS_ID = "urazy_mimo_udalosti"
_KNOWLEDGE_FILE = "urazy_mimo_udalosti.json"
_FIRST_SECTION_ID = "evidence_hlaseni_urazu"


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
    global AudityKnowledgeEditorDialog
    global AudityKnowledgeProcessEditorWidget
    global AudityKnowledgeSectionDialog

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import validate_all_catalogs
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
    from moduly.audity.ui.audity_knowledge_process_editor_widget import (
        AudityKnowledgeProcessEditorWidget,
    )
    from moduly.audity.ui.audity_knowledge_section_dialog import AudityKnowledgeSectionDialog


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
        self._knowledge_path = audit_knowledge_service.audity_dir / _KNOWLEDGE_FILE
        bundled = editable_catalog_service.bundled_path(f"audity/{_KNOWLEDGE_FILE}")
        shutil.copy2(bundled, self._knowledge_path)
        audit_knowledge_service.ensure_catalogs()
        with self._knowledge_path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._knowledge_path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _sections_from_file(self) -> list[dict]:
        with self._knowledge_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return list(payload.get("sekce") or [])

    def _section_by_id(self, section_id: str) -> dict | None:
        for section in self._sections_from_file():
            if section.get("id") == section_id:
                return section
        return None

    def _create_payload(self, **overrides) -> dict:
        payload = {
            "nazev": "Editor test — nová oblast ověření",
            "popis": "Editor test — popis nové oblasti.",
            "cil_overeni": "Editor test — cíl ověření nové oblasti.",
            "poradi": audit_knowledge_editor_service.suggest_next_section_poradi(_PROCESS_ID),
            "aktivni": True,
        }
        payload.update(overrides)
        return payload


class AudityKnowledgeSectionCreateServiceTestCase(_KnowledgeEditorTestBase):
    def test_create_section_adds_new_area(self) -> None:
        before_count = len(self._sections_from_file())
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [], msg="; ".join(errors))
        assert section_id is not None

        after_sections = self._sections_from_file()
        self.assertEqual(len(after_sections), before_count + 1)
        created = self._section_by_id(section_id)
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["nazev"], "Editor test — nová oblast ověření")

    def test_create_section_generates_id_from_nazev(self) -> None:
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(nazev="Editor test — nová oblast ověření"),
        )
        self.assertEqual(errors, [])
        assert section_id is not None
        self.assertEqual(section_id, "editor_test_nova_oblast_overeni")

    def test_create_section_rejects_duplicate_id(self) -> None:
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(
                id=_FIRST_SECTION_ID,
                nazev="Duplicitní oblast",
            ),
        )
        self.assertIsNone(section_id)
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(_FIRST_SECTION_ID, errors[0])

    def test_create_section_uses_default_poradi_plus_ten(self) -> None:
        expected = audit_knowledge_editor_service.suggest_next_section_poradi(_PROCESS_ID)
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(poradi=expected),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        created = self._section_by_id(section_id)
        assert created is not None
        self.assertEqual(created["poradi"], expected)
        self.assertGreater(expected, 0)

    def test_suggest_next_section_poradi_is_ten_for_empty_process(self) -> None:
        empty_knowledge = {"sekce": []}
        self.assertEqual(
            audit_knowledge_service.get_next_section_poradi(empty_knowledge),
            10,
        )

    def test_create_section_has_stable_structure(self) -> None:
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        created = self._section_by_id(section_id)
        assert created is not None
        for field in SECTION_REQUIRED_FIELDS:
            self.assertIn(field, created)
        for field, value in created.items():
            if field in {
                "id",
                "nazev",
                "popis",
                "cil_overeni",
                "poradi",
                "aktivni",
            }:
                continue
            self.assertIsInstance(value, list)
            self.assertEqual(value, [])

    def test_create_section_does_not_overwrite_existing_sections(self) -> None:
        before = self._sections_from_file()
        first_before = deepcopy(before[0])

        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        after = self._sections_from_file()
        self.assertEqual(after[0], first_before)
        self.assertEqual(len(after), len(before) + 1)

    def test_create_section_creates_backup(self) -> None:
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(nazev="Editor test — záloha nové oblasti"),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        backup_dir = audit_knowledge_editor_service.backup_dir()
        backups = list(backup_dir.glob(f"{_KNOWLEDGE_FILE}.*.bak"))
        self.assertGreaterEqual(len(backups), 1)

    def test_create_section_keeps_valid_json(self) -> None:
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        validation_errors = validate_all_catalogs(audit_knowledge_service.audity_dir)
        self.assertEqual(validation_errors, [])

    def test_create_section_refreshes_tree(self) -> None:
        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            self._create_payload(nazev="Editor test — refresh stromu oblasti"),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        roots = audit_knowledge_service.get_knowledge_tree(
            include_inactive=True,
            ensure=False,
        )
        process_node = next(root for root in roots if root.process_id == _PROCESS_ID)
        section_ids = {child.node_id for child in process_node.children}
        self.assertIn(section_id, section_ids)


class AudityKnowledgeSectionDialogTestCase(_KnowledgeEditorTestBase):
    def test_section_dialog_generates_read_only_id(self) -> None:
        dialog = AudityKnowledgeSectionDialog(
            existing_ids=set(),
            default_poradi=120,
        )
        dialog._nazev_edit.setText("Editor test — dialog oblasti")
        dialog._update_generated_id_preview()

        self.assertTrue(dialog._id_edit.isReadOnly())
        self.assertEqual(dialog._id_edit.text(), "editor_test_dialog_oblasti")
        self.assertEqual(dialog._poradi_spin.value(), 120)


class AudityKnowledgeEditorDialogAddSectionTestCase(_KnowledgeEditorTestBase):
    def test_dialog_add_section_selects_new_area(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        existing_ids = audit_knowledge_service.collect_section_ids(
            self._sections_from_file()
        )
        section_dialog = AudityKnowledgeSectionDialog(
            existing_ids=existing_ids,
            default_poradi=audit_knowledge_editor_service.suggest_next_section_poradi(
                _PROCESS_ID
            ),
        )
        section_dialog._nazev_edit.setText("Editor test — dialog integrace")
        section_dialog._popis_edit.setPlainText("Popis")
        section_dialog._cil_overeni_edit.setPlainText("Cíl")
        section_dialog._update_generated_id_preview()

        section_id, errors = audit_knowledge_editor_service.create_section(
            _PROCESS_ID,
            section_dialog.section_payload(),
        )
        self.assertEqual(errors, [])
        assert section_id is not None

        dialog.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID, section_id))
        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_SECTION)
        self.assertEqual(dialog.section_editor.section_id, section_id)


def deepcopy(value):
    return json.loads(json.dumps(value))


if __name__ == "__main__":
    unittest.main()
