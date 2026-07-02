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
    global validate_knowledge_file
    global validate_all_catalogs
    global AudityKnowledgeEditorDialog
    global AudityKnowledgeProcessEditorWidget
    global KNOWLEDGE_EDITOR_SAVED_MESSAGE

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.constants import KNOWLEDGE_EDITOR_SAVED_MESSAGE
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import (
        validate_all_catalogs,
        validate_knowledge_file,
    )
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
    from moduly.audity.ui.audity_knowledge_process_editor_widget import (
        AudityKnowledgeProcessEditorWidget,
    )


_bootstrap_storage()
_import_services()


class AudityKnowledgeProcessEditorServiceTestCase(unittest.TestCase):
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
        self._procesy_path = audit_knowledge_service.audity_dir / "procesy.json"
        bundled_knowledge = editable_catalog_service.bundled_path(
            f"audity/{_KNOWLEDGE_FILE}"
        )
        bundled_procesy = editable_catalog_service.bundled_path("audity/procesy.json")
        shutil.copy2(bundled_knowledge, self._knowledge_path)
        shutil.copy2(bundled_procesy, self._procesy_path)
        audit_knowledge_service.ensure_catalogs()
        with self._knowledge_path.open(encoding="utf-8") as handle:
            self._original_knowledge = json.load(handle)
        with self._procesy_path.open(encoding="utf-8") as handle:
            self._original_procesy = json.load(handle)

    def tearDown(self) -> None:
        self._knowledge_path.write_text(
            json.dumps(self._original_knowledge, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._procesy_path.write_text(
            json.dumps(self._original_procesy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _metadata_from_file(self) -> dict:
        with self._knowledge_path.open(encoding="utf-8") as handle:
            knowledge = json.load(handle)
        with self._procesy_path.open(encoding="utf-8") as handle:
            procesy = json.load(handle)
        registry = next(
            item for item in procesy.get("procesy") or [] if item.get("id") == _PROCESS_ID
        )
        return {
            "registry": registry,
            "knowledge": knowledge,
        }

    def _save_metadata(self, **changes) -> list[str]:
        current = audit_knowledge_service.get_process_metadata(_PROCESS_ID, ensure=False)
        assert current is not None
        metadata = {**current, **changes}
        return audit_knowledge_editor_service.save_process_metadata(_PROCESS_ID, metadata)

    def test_save_process_metadata_changes_nazev(self) -> None:
        errors = self._save_metadata(nazev="Editor test — název procesu")
        self.assertEqual(errors, [], msg="; ".join(errors))

        data = self._metadata_from_file()
        self.assertEqual(data["registry"]["nazev"], "Editor test — název procesu")
        self.assertEqual(data["knowledge"]["nazev"], "Editor test — název procesu")

    def test_save_process_metadata_changes_popis(self) -> None:
        errors = self._save_metadata(popis="Editor test — popis procesu.")
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        self.assertEqual(data["registry"]["popis"], "Editor test — popis procesu.")
        self.assertEqual(data["knowledge"]["popis"], "Editor test — popis procesu.")

    def test_save_process_metadata_changes_ucel_procesu(self) -> None:
        errors = self._save_metadata(ucel_procesu="Editor test — účel procesu.")
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        self.assertEqual(data["knowledge"]["ucel_procesu"], "Editor test — účel procesu.")

    def test_save_process_metadata_changes_proc_je_dulezity(self) -> None:
        errors = self._save_metadata(proc_je_dulezity="Editor test — proč je důležitý.")
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        self.assertEqual(
            data["knowledge"]["proc_je_dulezity"],
            "Editor test — proč je důležitý.",
        )

    def test_save_process_metadata_changes_ocekavany_vystup(self) -> None:
        errors = self._save_metadata(ocekavany_vystup="Editor test — očekávaný výstup.")
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        self.assertEqual(
            data["knowledge"]["ocekavany_vystup"],
            "Editor test — očekávaný výstup.",
        )

    def test_save_process_metadata_changes_poradi(self) -> None:
        errors = self._save_metadata(poradi=999)
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        self.assertEqual(data["registry"]["poradi"], 999)
        self.assertEqual(data["knowledge"]["poradi"], 999)

    def test_save_process_metadata_changes_aktivni(self) -> None:
        errors = self._save_metadata(aktivni=False)
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        self.assertFalse(data["registry"]["aktivni"])
        self.assertFalse(data["knowledge"]["aktivni"])

    def test_save_process_metadata_syncs_registry_and_knowledge(self) -> None:
        errors = self._save_metadata(
            nazev="Editor test — synchronizace",
            popis="Editor test — popis synchronizace.",
            poradi=888,
            aktivni=True,
        )
        self.assertEqual(errors, [])

        data = self._metadata_from_file()
        for field in ("nazev", "popis", "poradi", "aktivni"):
            self.assertEqual(data["registry"][field], data["knowledge"][field])

    def test_save_process_metadata_creates_backups(self) -> None:
        errors = self._save_metadata(nazev="Editor test — záloha procesu")
        self.assertEqual(errors, [])

        backup_dir = audit_knowledge_editor_service.backup_dir()
        knowledge_backups = list(backup_dir.glob(f"{_KNOWLEDGE_FILE}.*.bak"))
        procesy_backups = list(backup_dir.glob("procesy.json.*.bak"))
        self.assertGreaterEqual(len(knowledge_backups), 1)
        self.assertGreaterEqual(len(procesy_backups), 1)

    def test_save_process_metadata_keeps_valid_json(self) -> None:
        errors = self._save_metadata(nazev="Editor test — validace JSON")
        self.assertEqual(errors, [])

        validation_errors = validate_all_catalogs(audit_knowledge_service.audity_dir)
        self.assertEqual(validation_errors, [])

    def test_save_process_metadata_refreshes_tree_label(self) -> None:
        errors = self._save_metadata(nazev="Editor test — refresh stromu procesu")
        self.assertEqual(errors, [])

        roots = audit_knowledge_service.get_knowledge_tree(
            include_inactive=True,
            ensure=False,
        )
        process_node = next(root for root in roots if root.process_id == _PROCESS_ID)
        self.assertEqual(process_node.label, "Editor test — refresh stromu procesu")

    def test_empty_nazev_is_rejected(self) -> None:
        errors = self._save_metadata(nazev="   ")
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("Název procesu", errors[0])


class AudityKnowledgeProcessEditorWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        _bootstrap_storage()
        _import_services()
        cls._app = QApplication.instance() or QApplication([])

    def test_process_editor_exposes_metadata_fields(self) -> None:
        widget = AudityKnowledgeProcessEditorWidget()
        widget.load_process(
            process_id=_PROCESS_ID,
            metadata={
                "nazev": "Test proces",
                "popis": "Popis",
                "ucel_procesu": "Účel",
                "proc_je_dulezity": "Důležitost",
                "ocekavany_vystup": "Výstup",
                "poradi": 20,
                "aktivni": True,
            },
        )

        self.assertEqual(widget.process_id, _PROCESS_ID)
        metadata = widget.process_metadata()
        self.assertEqual(metadata["nazev"], "Test proces")
        self.assertEqual(metadata["ucel_procesu"], "Účel")
        self.assertEqual(metadata["poradi"], 20)
        self.assertTrue(metadata["aktivni"])


class AudityKnowledgeEditorDialogProcessTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        _bootstrap_storage()
        _import_services()
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_process_selection_enables_save(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        assert first_process is not None

        dialog.knowledge_tree.setCurrentItem(first_process)

        self.assertEqual(dialog.content_stack.currentIndex(), dialog._PAGE_PROCESS)
        self.assertTrue(dialog._apply_btn.isEnabled())
        self.assertTrue(dialog.process_editor.has_process())


class AudityKnowledgeEditorDialogSaveFeedbackTestCase(
    AudityKnowledgeProcessEditorServiceTestCase
):
    def test_save_success_shows_status_label(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        dialog.process_editor._nazev_edit.setText("Editor test — potvrzení uložení")
        dialog._apply_changes()

        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)

    @patch("moduly.audity.ui.audity_knowledge_editor_dialog.QMessageBox.warning")
    @patch(
        "moduly.audity.ui.audity_knowledge_editor_dialog.audit_knowledge_editor_service.save_process_metadata",
        return_value=["Editor test — simulovaná chyba uložení."],
    )
    def test_save_error_shows_message(self, _mock_save, mock_warning) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        dialog._apply_changes()

        mock_warning.assert_called_once()
        self.assertEqual(dialog._status_label.text(), "")


if __name__ == "__main__":
    unittest.main()
