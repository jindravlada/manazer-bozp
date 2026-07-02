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
_EXISTING_ITEM_ID = "dukaz_kniha_urazu"

_LIST_FIELD_CASES = (
    ("objektivni_dukazy", "Editor test — nový objektivní důkaz."),
    ("doporucene_rozhovory", "Editor test — nový rozhovor."),
    ("pozorovani_v_provozu", "Editor test — nové pozorování v provozu."),
    ("typicke_neshody", "Editor test — nová typická neshoda."),
    ("pkz", "Editor test — nové PKZ."),
    ("pozorovani", "Editor test — nové pozorování."),
    ("vazby_procesy", "Editor test — nová vazba."),
    ("pozadavky_normy", "Editor test — nová norma."),
)


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
    global AudityKnowledgeListEditorWidget
    global AudityKnowledgeListItemDialog
    global AudityKnowledgeSectionEditorWidget
    global KNOWLEDGE_EDITOR_SECTION_LIST_TABS

    from core.services.editable_catalog_service import editable_catalog_service
    from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_LIST_TABS
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import validate_knowledge_file
    from moduly.audity.ui.audity_knowledge_list_editor_widget import (
        AudityKnowledgeListEditorWidget,
    )
    from moduly.audity.ui.audity_knowledge_list_item_dialog import (
        AudityKnowledgeListItemDialog,
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

    def _item_by_id(self, field_name: str, item_id: str) -> dict | None:
        section = self._section_from_file()
        for item in section.get(field_name) or []:
            if item.get("id") == item_id:
                return item
        return None

    def _create_payload(self, text: str, **overrides) -> dict:
        payload = {
            "nazev": text,
            "poradi": 888,
            "aktivni": True,
        }
        payload.update(overrides)
        return payload


class AudityKnowledgeListEditorServiceTestCase(_KnowledgeEditorTestBase):
    def test_create_list_item(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload("Editor test — nový objektivní důkaz."),
        )
        self.assertEqual(errors, [], msg="; ".join(errors))

        created = self._item_by_id(
            "objektivni_dukazy",
            "editor_test_novy_objektivni_dukaz",
        )
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["nazev"], "Editor test — nový objektivní důkaz.")

    def test_edit_list_item(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload(
                "Editor test — upravený objektivní důkaz.",
                poradi=777,
            ),
            item_id=_EXISTING_ITEM_ID,
        )
        self.assertEqual(errors, [])

        updated = self._item_by_id("objektivni_dukazy", _EXISTING_ITEM_ID)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["id"], _EXISTING_ITEM_ID)
        self.assertEqual(updated["nazev"], "Editor test — upravený objektivní důkaz.")
        self.assertEqual(updated["poradi"], 777)

    def test_deactivate_list_item(self) -> None:
        errors = audit_knowledge_editor_service.set_section_list_item_active(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            _EXISTING_ITEM_ID,
            aktivni=False,
        )
        self.assertEqual(errors, [])

        updated = self._item_by_id("objektivni_dukazy", _EXISTING_ITEM_ID)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertFalse(updated["aktivni"])

    def test_restore_list_item(self) -> None:
        deactivate_errors = audit_knowledge_editor_service.set_section_list_item_active(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            _EXISTING_ITEM_ID,
            aktivni=False,
        )
        self.assertEqual(deactivate_errors, [])

        restore_errors = audit_knowledge_editor_service.set_section_list_item_active(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            _EXISTING_ITEM_ID,
            aktivni=True,
        )
        self.assertEqual(restore_errors, [])

        updated = self._item_by_id("objektivni_dukazy", _EXISTING_ITEM_ID)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertTrue(updated["aktivni"])

    def test_edit_preserves_id(self) -> None:
        before = self._item_by_id("objektivni_dukazy", _EXISTING_ITEM_ID)
        assert before is not None

        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload("Editor test — ID zůstává."),
            item_id=_EXISTING_ITEM_ID,
        )
        self.assertEqual(errors, [])

        after = self._item_by_id("objektivni_dukazy", _EXISTING_ITEM_ID)
        self.assertIsNotNone(after)
        assert after is not None
        self.assertEqual(after["id"], before["id"])

    def test_create_list_item_creates_backup(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload("Editor test — záloha seznamu."),
        )
        self.assertEqual(errors, [])

        backup_dir = audit_knowledge_editor_service.backup_dir()
        backups = list(backup_dir.glob("urazy_mimo_udalosti.json.*.bak"))
        self.assertGreaterEqual(len(backups), 1)

    def test_create_list_item_keeps_valid_json(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload("Editor test — validace JSON."),
        )
        self.assertEqual(errors, [])

        validation_errors = validate_knowledge_file(self._path)
        self.assertEqual(validation_errors, [])

    def test_empty_text_is_rejected(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload("   "),
        )
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("Text položky", errors[0])

    def test_refresh_list_after_save(self) -> None:
        errors = audit_knowledge_editor_service.save_section_list_item(
            _PROCESS_ID,
            _SECTION_ID,
            "objektivni_dukazy",
            self._create_payload("Editor test — refresh seznamu."),
        )
        self.assertEqual(errors, [])

        section = audit_knowledge_service.get_criterion(
            _PROCESS_ID,
            _SECTION_ID,
            ensure=False,
        )
        assert section is not None
        normalized = audit_knowledge_service.normalize_list_items(
            section.get("objektivni_dukazy") or []
        )
        names = {item["nazev"] for item in normalized}
        self.assertIn("Editor test — refresh seznamu.", names)

    def test_all_editor_list_fields(self) -> None:
        for field_name, text in _LIST_FIELD_CASES:
            with self.subTest(field_name=field_name):
                errors = audit_knowledge_editor_service.save_section_list_item(
                    _PROCESS_ID,
                    _SECTION_ID,
                    field_name,
                    self._create_payload(text),
                )
                self.assertEqual(errors, [], msg="; ".join(errors))

                section = audit_knowledge_service.get_criterion(
                    _PROCESS_ID,
                    _SECTION_ID,
                    ensure=False,
                )
                assert section is not None
                normalized = audit_knowledge_service.normalize_list_items(
                    section.get(field_name) or []
                )
                names = {item["nazev"] for item in normalized}
                self.assertIn(text, names)


class AudityKnowledgeListEditorWidgetTestCase(_KnowledgeEditorTestBase):
    def test_list_editor_widget_loads_table(self) -> None:
        section = self._section_from_file()
        widget = AudityKnowledgeListEditorWidget("objektivni_dukazy")
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

    def test_list_item_dialog_edit_mode_keeps_id_read_only(self) -> None:
        section = self._section_from_file()
        item = next(
            entry
            for entry in section.get("objektivni_dukazy") or []
            if entry.get("id") == _EXISTING_ITEM_ID
        )
        dialog = AudityKnowledgeListItemDialog(item=item)
        self.assertTrue(dialog._id_edit.isReadOnly())
        self.assertEqual(dialog.editing_item_id, _EXISTING_ITEM_ID)


class AudityKnowledgeSectionEditorListTabsTestCase(_KnowledgeEditorTestBase):
    def test_section_editor_has_list_widgets_for_all_tabs(self) -> None:
        widget = AudityKnowledgeSectionEditorWidget()
        section = self._section_from_file()
        widget.load_section(
            process_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            section=section,
        )

        self.assertEqual(
            widget._tabs.count(),
            len(KNOWLEDGE_EDITOR_SECTION_LIST_TABS) + 3,
        )
        self.assertEqual(len(widget._list_widgets), len(KNOWLEDGE_EDITOR_SECTION_LIST_TABS))

        for title, field_name in KNOWLEDGE_EDITOR_SECTION_LIST_TABS:
            with self.subTest(field_name=field_name):
                self.assertIn(field_name, widget._list_widgets)
                tab_index = next(
                    index
                    for index in range(widget._tabs.count())
                    if widget._tabs.tabText(index) == title
                )
                self.assertIs(
                    widget._tabs.widget(tab_index),
                    widget._list_widgets[field_name],
                )


if __name__ == "__main__":
    unittest.main()
