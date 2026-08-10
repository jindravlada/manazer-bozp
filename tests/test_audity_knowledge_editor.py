import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from core.services.editable_catalog_service import (
        EDITABLE_CATALOGS,
        editable_catalog_service,
    )
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import (
        EDITABLE_SECTION_ASSERTION_FIELDS,
        EDITABLE_SECTION_LIST_FIELDS,
    )
    from moduly.audity.sluzby.audit_knowledge_validator import (
        default_audity_dir,
        normalize_legacy_knowledge_data,
        validate_all_catalogs,
        validate_knowledge_data,
    )


class AudityKnowledgeEditorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_editable_fields_include_methodology_sections(self) -> None:
        assertion_fields = {field for _label, field in EDITABLE_SECTION_ASSERTION_FIELDS}
        list_fields = {field for _label, field in EDITABLE_SECTION_LIST_FIELDS}

        self.assertIn("auditni_tvrzeni", assertion_fields)
        self.assertIn("doporucene_rozhovory", list_fields)
        self.assertIn("pozorovani_v_provozu", list_fields)

    def test_all_audity_knowledge_files_are_registered(self) -> None:
        errors = validate_all_catalogs(default_audity_dir())
        self.assertEqual(errors, [])

        registered = set(editable_catalog_service.registered_paths())
        self.assertIn("audity/procesy.json", registered)

        procesy_path = default_audity_dir() / "procesy.json"
        with procesy_path.open(encoding="utf-8") as handle:
            registry = json.load(handle)

        for process in registry.get("procesy") or []:
            soubor = str(process.get("soubor_znalosti") or "").strip()
            with self.subTest(soubor=soubor):
                self.assertTrue(soubor)
                self.assertIn(f"audity/{soubor}", registered)

        audity_catalogs = [
            catalog.relative_path
            for catalog in EDITABLE_CATALOGS
            if catalog.relative_path.startswith("audity/")
        ]
        self.assertGreaterEqual(len(audity_catalogs), 28)

    def test_assert_user_writable_path_blocks_bundled_seed(self) -> None:
        bundled_file = editable_catalog_service.bundled_path(
            "audity/urazy_mimo_udalosti.json"
        )
        with self.assertRaises(PermissionError):
            audit_knowledge_editor_service.assert_user_writable_path(bundled_file)

    def test_load_all_knowledge_files_from_user_copy(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        result = audit_knowledge_editor_service.load_all_knowledge_files()

        self.assertEqual(result.errors, ())
        self.assertGreaterEqual(len(result.files), 1)
        for loaded in result.files:
            self.assertTrue(loaded.relative_path.startswith("audity/"))
            self.assertIsInstance(loaded.data, dict)
            self.assertTrue(str(loaded.data.get("id") or "").strip())

    def test_validate_no_list_items_removed(self) -> None:
        before = [{"id": "a", "nazev": "A"}, {"id": "b", "nazev": "B"}]
        after = [
            {"id": "a", "nazev": "A"},
            {"id": "b", "nazev": "B", "aktivni": False},
        ]

        errors = audit_knowledge_editor_service.validate_no_list_items_removed(
            before,
            after,
            path="sekce.test.auditni_tvrzeni",
        )
        self.assertEqual(errors, [])

        errors = audit_knowledge_editor_service.validate_no_list_items_removed(
            before,
            [{"id": "a", "nazev": "A"}],
            path="sekce.test.auditni_tvrzeni",
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("b", errors[0])

    def test_normalize_legacy_knowledge_data_fills_missing_section_lists(self) -> None:
        data = {
            "verze": 1,
            "id": "planovani_bozp",
            "nazev": "Test",
            "popis": "",
            "ucel_procesu": "",
            "proc_je_dulezity": "",
            "ocekavany_vystup": "",
            "poradi": 1,
            "aktivni": True,
            "sekce": [
                {
                    "id": "cile_politika",
                    "nazev": "Cíle a politika",
                    "popis": "",
                    "cil_overeni": "",
                    "poradi": 1,
                    "aktivni": True,
                    "auditni_tvrzeni": [
                        {
                            "id": "legacy_bez_popisu",
                            "text": "Legacy tvrzení",
                            "poradi": 10,
                            "aktivni": True,
                            "zavaznost": "stredni",
                        }
                    ],
                }
            ],
        }

        normalize_legacy_knowledge_data(data)

        section = data["sekce"][0]
        for field in (
            "navodne_otazky",
            "objektivni_dukazy",
            "doporucene_rozhovory",
            "pozorovani_v_provozu",
            "typicke_neshody",
            "pkz",
            "pozorovani",
            "vazby_procesy",
            "pozadavky_normy",
            "postup_kontroly",
            "referencni_fotografie",
        ):
            with self.subTest(field=field):
                self.assertEqual(section[field], [])

        assertion = section["auditni_tvrzeni"][0]
        self.assertEqual(assertion["popis"], "")
        self.assertEqual(assertion["verification_type"], "dokumentace")
        self.assertEqual(assertion["text"], "Legacy tvrzení")

        errors = validate_knowledge_data(data, source_name="planovani_bozp.json")
        self.assertEqual(errors, [])

    def test_save_section_metadata_accepts_legacy_section_without_list_fields(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        relative_path = "audity/planovani_bozp.json"
        path = audit_knowledge_editor_service.resolve_user_path(relative_path)

        with path.open(encoding="utf-8") as handle:
            original = json.load(handle)

        try:
            legacy = json.loads(json.dumps(original))
            section = next(
                item
                for item in legacy.get("sekce") or []
                if item.get("id") == "cile_politika"
            )
            for field in (
                "navodne_otazky",
                "auditni_tvrzeni",
                "objektivni_dukazy",
                "doporucene_rozhovory",
                "pozorovani_v_provozu",
                "typicke_neshody",
                "pkz",
                "pozorovani",
                "vazby_procesy",
                "pozadavky_normy",
                "postup_kontroly",
                "referencni_fotografie",
            ):
                section.pop(field, None)

            errors = audit_knowledge_editor_service.save_user_json(relative_path, legacy)
            self.assertEqual(errors, [])

            with path.open(encoding="utf-8") as handle:
                saved = json.load(handle)
            saved_section = next(
                item
                for item in saved.get("sekce") or []
                if item.get("id") == "cile_politika"
            )
            self.assertEqual(saved_section.get("navodne_otazky"), [])
            self.assertEqual(saved_section.get("auditni_tvrzeni"), [])
        finally:
            path.write_text(
                json.dumps(original, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def test_save_user_json_creates_backup_and_writes_atomically(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        relative_path = "audity/urazy_mimo_udalosti.json"
        path = audit_knowledge_editor_service.resolve_user_path(relative_path)

        with path.open(encoding="utf-8") as handle:
            original = json.load(handle)

        try:
            modified = json.loads(json.dumps(original))
            section = modified["sekce"][0]
            assertions = section.get("auditni_tvrzeni") or []
            if assertions:
                assertions[0] = {
                    **assertions[0],
                    "text": "Testovací úprava editoru metodiky.",
                }

            errors = audit_knowledge_editor_service.save_user_json(relative_path, modified)
            self.assertEqual(errors, [])

            backup_dir = audit_knowledge_editor_service.backup_dir()
            backups = list(backup_dir.glob("urazy_mimo_udalosti.json.*.bak"))
            self.assertGreaterEqual(len(backups), 1)
            self.assertFalse(path.with_name(f"{path.name}.tmp").exists())

            with path.open(encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(
                saved["sekce"][0]["auditni_tvrzeni"][0]["text"],
                "Testovací úprava editoru metodiky.",
            )
        finally:
            path.write_text(
                json.dumps(original, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def test_save_user_json_rejects_invalid_data(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        relative_path = "audity/urazy_mimo_udalosti.json"
        path = audit_knowledge_editor_service.resolve_user_path(relative_path)

        with path.open(encoding="utf-8") as handle:
            original_text = handle.read()

        invalid = {"id": "wrong_id", "verze": 1}
        errors = audit_knowledge_editor_service.save_user_json(relative_path, invalid)
        self.assertGreater(len(errors), 0)

        with path.open(encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original_text)

    def test_validate_user_catalogs_after_ensure(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        errors = audit_knowledge_editor_service.validate_user_catalogs()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
