import importlib
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.sprava_dat.sluzby.codebook_capabilities import capabilities_for
    from moduly.sprava_dat.sluzby.codebook_catalog_service import (
        MODULE_KNIHA_URAZU,
        MODULE_OTHER,
        MODULE_RIDICI,
        STORAGE_BUNDLED_JSON,
        STORAGE_DATABASE,
        STORAGE_HARDCODED,
        CodebookEntry,
        codebook_catalog_service,
        _KIND_DATABASE,
        _KIND_HARDCODED,
        _KIND_JSON_BUNDLED,
        _KIND_JSON_WORKSPACE,
    )
    from moduly.sprava_dat.sluzby.data_management_settings_service import data_management_settings_service
    from moduly.sprava_dat.ui.codebooks_tab import CodebooksTab


def _entry(**overrides) -> CodebookEntry:
    base = {
        "codebook_id": "json:test/sample.json",
        "name": "Ukázkový číselník",
        "module": MODULE_OTHER,
        "storage_type": STORAGE_BUNDLED_JSON,
        "path": "/tmp/sample.json",
        "item_count": 1,
        "last_modified": None,
        "exportable": True,
        "importable": True,
        "kind": _KIND_JSON_WORKSPACE,
        "relative_path": "test/sample.json",
    }
    base.update(overrides)
    return CodebookEntry(**base)


class CodebookCapabilitiesPhase91dTestCase(unittest.TestCase):
    def test_editable_codebook_supports_import(self) -> None:
        entry = _entry(importable=True, kind=_KIND_JSON_WORKSPACE, storage_type="JSON")
        capabilities = capabilities_for(entry)
        self.assertTrue(capabilities.import_supported)
        self.assertTrue(capabilities.shows_import_action)
        self.assertFalse(capabilities.shows_import_info)

    def test_bundled_database_codebook_shows_reason(self) -> None:
        entry = codebook_catalog_service.get_by_id("bundled:cz_nace")
        self.assertIsNotNone(entry)
        assert entry is not None
        capabilities = capabilities_for(entry)
        self.assertFalse(capabilities.import_supported)
        self.assertTrue(capabilities.shows_import_info)
        self.assertIn("distribuované databáze", capabilities.import_unavailable_reason)

    def test_installation_builtin_codebook_shows_reason(self) -> None:
        entry = codebook_catalog_service.get_by_id("hardcoded:okresy")
        self.assertIsNotNone(entry)
        assert entry is not None
        capabilities = capabilities_for(entry)
        self.assertIn("instalace programu", capabilities.import_unavailable_headline)
        self.assertIn("Součást instalace programu", capabilities.import_unavailable_reason)

    def test_distributed_reference_codebook_shows_reason(self) -> None:
        entry = codebook_catalog_service.get_by_id("hardcoded:zdravotni_pojistovny")
        self.assertIsNotNone(entry)
        assert entry is not None
        capabilities = capabilities_for(entry)
        self.assertIn("referenční", capabilities.import_unavailable_reason)

    def test_capability_change_switches_ui_mode(self) -> None:
        entry = _entry(
            codebook_id="bundled:demo",
            kind=_KIND_JSON_BUNDLED,
            storage_type=STORAGE_BUNDLED_JSON,
            importable=False,
        )
        blocked = capabilities_for(entry)
        self.assertTrue(blocked.shows_import_info)

        editable = capabilities_for(replace(entry, importable=True))
        self.assertTrue(editable.shows_import_action)
        self.assertFalse(editable.shows_import_info)


class CodebooksTabImportUxPhase91dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = CodebooksTab()

    def _import_buttons(self) -> list[QPushButton]:
        return [
            button
            for button in self.tab.findChildren(QPushButton)
            if button.text() == "Import"
        ]

    def test_editable_codebook_shows_export_and_import_buttons(self) -> None:
        entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.tab._show_entry_details(entry)

        self.assertTrue(self.tab.export_button.isEnabled())
        self.assertFalse(self.tab.import_button.isHidden())
        self.assertTrue(self.tab.import_button.isEnabled())
        self.assertTrue(self.tab.import_info_widget.isHidden())

    def test_distributed_codebook_shows_info_panel_instead_of_import(self) -> None:
        entry = codebook_catalog_service.get_by_id("bundled:cz_nace")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.tab._show_entry_details(entry)

        self.assertTrue(self.tab.export_button.isEnabled())
        self.assertTrue(self.tab.import_button.isHidden())
        self.assertFalse(any(not button.isHidden() for button in self._import_buttons()))
        self.assertFalse(self.tab.import_info_widget.isHidden())
        self.assertIn("distribuované databáze", self.tab.import_info_reason.text())

    def test_no_disabled_import_button_remains_for_non_importable_entries(self) -> None:
        non_importable_ids = (
            "bundled:cz_nace",
            "hardcoded:okresy",
            "hardcoded:zdravotni_pojistovny",
            "db:control_processes",
        )
        for codebook_id in non_importable_ids:
            with self.subTest(codebook_id=codebook_id):
                entry = codebook_catalog_service.get_by_id(codebook_id)
                self.assertIsNotNone(entry)
                assert entry is not None
                self.tab._show_entry_details(entry)
                visible_import_buttons = [
                    button for button in self._import_buttons() if not button.isHidden()
                ]
                self.assertEqual(visible_import_buttons, [])
                self.assertFalse(self.tab.import_info_widget.isHidden())


if __name__ == "__main__":
    unittest.main()
