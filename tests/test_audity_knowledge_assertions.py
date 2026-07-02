import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QTableWidget

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)

_STORAGE_BOOTSTRAPPED = False

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_EXISTING_ASSERTION_ID = "vsechny_urazy_evidovany"


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
    global AudityKnowledgeAssertionDialog
    global AudityKnowledgeAssertionsWidget
    global AudityKnowledgeSectionEditorWidget
    global KNOWLEDGE_EDITOR_TAB_PLACEHOLDER

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.constants import KNOWLEDGE_EDITOR_TAB_PLACEHOLDER
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import validate_knowledge_file
    from moduly.audity.ui.audity_knowledge_assertion_dialog import (
        AudityKnowledgeAssertionDialog,
    )
    from moduly.audity.ui.audity_knowledge_assertions_widget import (
        AudityKnowledgeAssertionsWidget,
    )
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

    def _section_from_file(self) -> dict:
        process = audit_knowledge_service.get_process_by_id(_PROCESS_ID, ensure=False)
        assert process is not None and process.soubor_znalosti
        with (audit_knowledge_service.audity_dir / process.soubor_znalosti).open(
            encoding="utf-8"
        ) as handle:
            payload = json.load(handle)
        return next(
            item for item in payload.get("sekce") or [] if item.get("id") == _SECTION_ID
        )

    def _assertion_by_id(self, assertion_id: str) -> dict | None:
        section = self._section_from_file()
        for item in section.get("auditni_tvrzeni") or []:
            if item.get("id") == assertion_id:
                return item
        return None


class AudityKnowledgeAssertionsServiceTestCase(_KnowledgeEditorTestBase):
    def _create_payload(self, **overrides) -> dict:
        payload = {
            "text": "Editor test — nové auditní tvrzení.",
            "popis": "Editor test — popis tvrzení.",
            "poradi": 888,
            "aktivni": True,
            "zavaznost": "stredni",
        }
        payload.update(overrides)
        return payload

    def test_create_assertion(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [], msg="; ".join(errors))

        created = self._assertion_by_id("editor_test_nove_auditni_tvrzeni")
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["text"], "Editor test — nové auditní tvrzení.")
        self.assertEqual(created["poradi"], 888)

    def test_edit_assertion(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(
                text="Editor test — upravený text.",
                popis="Editor test — upravený popis.",
                poradi=777,
                zavaznost="kriticka",
            ),
            assertion_id=_EXISTING_ASSERTION_ID,
        )
        self.assertEqual(errors, [])

        updated = self._assertion_by_id(_EXISTING_ASSERTION_ID)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["id"], _EXISTING_ASSERTION_ID)
        self.assertEqual(updated["text"], "Editor test — upravený text.")
        self.assertEqual(updated["popis"], "Editor test — upravený popis.")
        self.assertEqual(updated["poradi"], 777)
        self.assertEqual(updated["zavaznost"], "kriticka")

    def test_deactivate_assertion(self) -> None:
        errors = audit_knowledge_editor_service.set_assertion_active(
            _PROCESS_ID,
            _SECTION_ID,
            _EXISTING_ASSERTION_ID,
            aktivni=False,
        )
        self.assertEqual(errors, [])

        updated = self._assertion_by_id(_EXISTING_ASSERTION_ID)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertFalse(updated["aktivni"])

    def test_restore_assertion(self) -> None:
        deactivate_errors = audit_knowledge_editor_service.set_assertion_active(
            _PROCESS_ID,
            _SECTION_ID,
            _EXISTING_ASSERTION_ID,
            aktivni=False,
        )
        self.assertEqual(deactivate_errors, [])

        restore_errors = audit_knowledge_editor_service.set_assertion_active(
            _PROCESS_ID,
            _SECTION_ID,
            _EXISTING_ASSERTION_ID,
            aktivni=True,
        )
        self.assertEqual(restore_errors, [])

        updated = self._assertion_by_id(_EXISTING_ASSERTION_ID)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertTrue(updated["aktivni"])

    def test_edit_preserves_id(self) -> None:
        before = self._assertion_by_id(_EXISTING_ASSERTION_ID)
        assert before is not None

        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(text="Editor test — ID zůstává."),
            assertion_id=_EXISTING_ASSERTION_ID,
        )
        self.assertEqual(errors, [])

        after = self._assertion_by_id(_EXISTING_ASSERTION_ID)
        self.assertIsNotNone(after)
        assert after is not None
        self.assertEqual(after["id"], before["id"])

    def test_create_assertion_creates_backup(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [])

        backup_dir = audit_knowledge_editor_service.backup_dir()
        backups = list(backup_dir.glob("urazy_mimo_udalosti.json.*.bak"))
        self.assertGreaterEqual(len(backups), 1)

    def test_create_assertion_keeps_valid_json(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(),
        )
        self.assertEqual(errors, [])

        validation_errors = validate_knowledge_file(self._path)
        self.assertEqual(validation_errors, [])

    def test_empty_text_is_rejected(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(text="   "),
        )
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("Text auditního tvrzení", errors[0])

    def test_refresh_list_after_save(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            self._create_payload(text="Editor test — refresh seznamu."),
        )
        self.assertEqual(errors, [])

        section = audit_knowledge_service.get_criterion(
            _PROCESS_ID,
            _SECTION_ID,
            ensure=False,
        )
        assert section is not None
        normalized = audit_knowledge_service.normalize_auditni_tvrzeni(
            section.get("auditni_tvrzeni") or []
        )
        texts = {item["text"] for item in normalized}
        self.assertIn("Editor test — refresh seznamu.", texts)


class AudityKnowledgeAssertionsWidgetTestCase(_KnowledgeEditorTestBase):
    def test_assertions_widget_loads_table(self) -> None:
        section = self._section_from_file()
        widget = AudityKnowledgeAssertionsWidget()
        widget.load_section(
            process_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            section=section,
        )

        table = widget.findChild(QTableWidget)
        self.assertIsNotNone(table)
        assert table is not None
        self.assertGreater(table.rowCount(), 0)
        self.assertTrue(widget._add_btn.isEnabled())

    def test_assertion_dialog_edit_mode_keeps_id_read_only(self) -> None:
        section = self._section_from_file()
        assertion = next(
            item
            for item in section.get("auditni_tvrzeni") or []
            if item.get("id") == _EXISTING_ASSERTION_ID
        )
        dialog = AudityKnowledgeAssertionDialog(assertion=assertion)
        self.assertTrue(dialog._id_edit.isReadOnly())
        self.assertEqual(dialog.editing_assertion_id, _EXISTING_ASSERTION_ID)


class AudityKnowledgeSectionEditorAssertionsTabTestCase(_KnowledgeEditorTestBase):
    def test_section_editor_first_tab_is_assertions(self) -> None:
        from PySide6.QtWidgets import QLabel

        widget = AudityKnowledgeSectionEditorWidget()
        section = self._section_from_file()
        widget.load_section(
            process_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            section=section,
        )

        self.assertEqual(widget._tabs.tabText(0), "Auditní tvrzení")
        self.assertIs(widget._tabs.widget(0), widget._assertions_widget)

        placeholder_tab = widget._tabs.widget(1)
        label = placeholder_tab.findChild(QLabel)
        self.assertIsNotNone(label)
        assert label is not None
        self.assertIn(KNOWLEDGE_EDITOR_TAB_PLACEHOLDER, label.text())


if __name__ == "__main__":
    unittest.main()
