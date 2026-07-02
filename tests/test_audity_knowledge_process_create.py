import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moduly.audity.sluzby.audit_knowledge_validator import PROCESS_REQUIRED_FIELDS

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)

_STORAGE_BOOTSTRAPPED = False

_PROCESS_ID = "urazy_mimo_udalosti"
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
    global AudityKnowledgeEditorDialog
    global AudityKnowledgeProcessCreateDialog

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import validate_all_catalogs
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
    from moduly.audity.ui.audity_knowledge_process_create_dialog import (
        AudityKnowledgeProcessCreateDialog,
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
        self._audity_dir = audit_knowledge_service.audity_dir
        self._procesy_path = self._audity_dir / "procesy.json"
        bundled_procesy = editable_catalog_service.bundled_path("audity/procesy.json")
        shutil.copy2(bundled_procesy, self._procesy_path)
        audit_knowledge_service.ensure_catalogs()
        with self._procesy_path.open(encoding="utf-8") as handle:
            self._original_procesy = json.load(handle)

    def tearDown(self) -> None:
        self._procesy_path.write_text(
            json.dumps(self._original_procesy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for path in self._audity_dir.glob("editor_test_*.json"):
            if path.is_file():
                path.unlink()

    def _create_payload(self, **overrides) -> dict:
        payload = {
            "nazev": "Editor test — nový řídicí proces",
            "popis": "Editor test — popis nového procesu.",
            "ucel_procesu": "Editor test — účel nového procesu.",
            "proc_je_dulezity": "Editor test — proč je důležitý.",
            "ocekavany_vystup": "Editor test — očekávaný výstup.",
            "poradi": audit_knowledge_editor_service.suggest_next_process_poradi(),
            "aktivni": True,
        }
        payload.update(overrides)
        return payload

    def _registry_entry(self, process_id: str) -> dict | None:
        with self._procesy_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload.get("procesy") or []:
            if item.get("id") == process_id:
                return item
        return None

    def _knowledge_file(self, process_id: str) -> dict | None:
        path = self._audity_dir / f"{process_id}.json"
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)


class AudityKnowledgeProcessCreateServiceTestCase(_KnowledgeEditorTestBase):
    def test_create_process_adds_registry_and_knowledge_file(self) -> None:
        before_count = len(self._original_procesy.get("procesy") or [])
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(),
        )
        self.assertEqual(errors, [], msg="; ".join(errors))
        assert process_id is not None

        with self._procesy_path.open(encoding="utf-8") as handle:
            procesy = json.load(handle)
        self.assertEqual(len(procesy.get("procesy") or []), before_count + 1)

        registry = self._registry_entry(process_id)
        self.assertIsNotNone(registry)
        assert registry is not None
        self.assertEqual(registry["soubor_znalosti"], f"{process_id}.json")

        knowledge = self._knowledge_file(process_id)
        self.assertIsNotNone(knowledge)
        assert knowledge is not None
        self.assertEqual(knowledge["nazev"], "Editor test — nový řídicí proces")

    def test_create_process_generates_id_from_nazev(self) -> None:
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(nazev="Editor test — nový řídicí proces"),
        )
        self.assertEqual(errors, [])
        assert process_id is not None
        self.assertEqual(process_id, "editor_test_novy_ridici_proces")

    def test_create_process_rejects_duplicate_id(self) -> None:
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(
                id=_PROCESS_ID,
                nazev="Duplicitní proces",
            ),
        )
        self.assertIsNone(process_id)
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(_PROCESS_ID, errors[0])

    def test_create_process_uses_default_poradi_plus_ten(self) -> None:
        expected = audit_knowledge_editor_service.suggest_next_process_poradi()
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(poradi=expected),
        )
        self.assertEqual(errors, [])
        assert process_id is not None

        registry = self._registry_entry(process_id)
        knowledge = self._knowledge_file(process_id)
        assert registry is not None
        assert knowledge is not None
        self.assertEqual(registry["poradi"], expected)
        self.assertEqual(knowledge["poradi"], expected)
        self.assertGreater(expected, 0)

    def test_suggest_next_process_poradi_is_ten_for_empty_registry(self) -> None:
        with patch.object(
            audit_knowledge_editor_service,
            "ensure_user_catalogs",
        ), patch.object(
            audit_knowledge_editor_service,
            "load_json_safe",
            return_value=({"procesy": []}, None),
        ):
            self.assertEqual(
                audit_knowledge_editor_service.suggest_next_process_poradi(),
                10,
            )

    def test_create_process_has_stable_structure(self) -> None:
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(),
        )
        self.assertEqual(errors, [])
        assert process_id is not None

        knowledge = self._knowledge_file(process_id)
        assert knowledge is not None
        for field in PROCESS_REQUIRED_FIELDS:
            self.assertIn(field, knowledge)
        self.assertEqual(knowledge["vazby_procesy"], [])
        self.assertEqual(knowledge["pozadavky_norem"], [])
        self.assertEqual(knowledge["sekce"], [])
        self.assertEqual(knowledge["zavaznost_seed_sync"], 1)

    def test_create_process_creates_backups(self) -> None:
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(nazev="Editor test — záloha procesu"),
        )
        self.assertEqual(errors, [])
        assert process_id is not None

        backup_dir = audit_knowledge_editor_service.backup_dir()
        procesy_backups = list(backup_dir.glob("procesy.json.*.bak"))
        self.assertGreaterEqual(len(procesy_backups), 1)

    def test_create_process_keeps_valid_json(self) -> None:
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(),
        )
        self.assertEqual(errors, [])
        assert process_id is not None

        validation_errors = validate_all_catalogs(audit_knowledge_service.audity_dir)
        self.assertEqual(validation_errors, [])

    def test_create_process_refreshes_tree(self) -> None:
        process_id, errors = audit_knowledge_editor_service.create_process(
            self._create_payload(nazev="Editor test — refresh stromu procesu"),
        )
        self.assertEqual(errors, [])
        assert process_id is not None

        roots = audit_knowledge_service.get_knowledge_tree(
            include_inactive=True,
            ensure=False,
        )
        process_ids = {root.process_id for root in roots}
        self.assertIn(process_id, process_ids)

    def test_create_process_rolls_back_on_write_failure(self) -> None:
        original_write = audit_knowledge_editor_service.atomic_write_json
        call_count = {"value": 0}

        def failing_write(path: Path, data: dict) -> None:
            call_count["value"] += 1
            if call_count["value"] == 2:
                raise OSError("simulovaná chyba zápisu")
            original_write(path, data)

        before_count = len(self._original_procesy.get("procesy") or [])
        with patch.object(
            audit_knowledge_editor_service,
            "atomic_write_json",
            side_effect=failing_write,
        ):
            process_id, errors = audit_knowledge_editor_service.create_process(
                self._create_payload(nazev="Editor test — rollback procesu"),
            )

        self.assertIsNone(process_id)
        self.assertGreaterEqual(len(errors), 1)

        with self._procesy_path.open(encoding="utf-8") as handle:
            procesy = json.load(handle)
        self.assertEqual(len(procesy.get("procesy") or []), before_count)
        self.assertFalse(
            (self._audity_dir / "editor_test_rollback_procesu.json").is_file()
        )


class AudityKnowledgeProcessCreateDialogTestCase(_KnowledgeEditorTestBase):
    def test_process_dialog_generates_read_only_id(self) -> None:
        dialog = AudityKnowledgeProcessCreateDialog(
            existing_ids=set(),
            default_poradi=250,
        )
        dialog._nazev_edit.setText("Editor test — dialog procesu")
        dialog._update_generated_id_preview()

        self.assertTrue(dialog._id_edit.isReadOnly())
        self.assertEqual(dialog._id_edit.text(), "editor_test_dialog_procesu")
        self.assertEqual(dialog._poradi_spin.value(), 250)


class AudityKnowledgeEditorDialogAddProcessTestCase(_KnowledgeEditorTestBase):
    def test_dialog_add_process_selects_new_process(self) -> None:
        dialog = AudityKnowledgeEditorDialog()

        process_dialog = AudityKnowledgeProcessCreateDialog(
            existing_ids=audit_knowledge_editor_service.collect_process_ids(),
            default_poradi=audit_knowledge_editor_service.suggest_next_process_poradi(),
        )
        process_dialog._nazev_edit.setText("Editor test — dialog integrace procesu")
        process_dialog._popis_edit.setPlainText("Popis")
        process_dialog._ucel_edit.setPlainText("Účel")
        process_dialog._update_generated_id_preview()

        process_id, errors = audit_knowledge_editor_service.create_process(
            process_dialog.process_payload(),
        )
        self.assertEqual(errors, [])
        assert process_id is not None

        dialog.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        self.assertTrue(dialog.knowledge_tree.select_node(process_id))
        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_PROCESS)
        self.assertEqual(dialog.process_editor.process_id, process_id)
        self.assertTrue(dialog._apply_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
