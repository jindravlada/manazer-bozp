"""AUDIT-FIELD-OFFICE-4: kompatibilita starších auditních tvrzení bez popisu."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="audit-field-office-4-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)
_HOME_PATCHER.start()

import core.services.editable_catalog_service as editable_catalog_module
import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()
importlib.reload(editable_catalog_module)

import moduly.audity.sluzby.audit_knowledge_editor_service as editor_module
import moduly.audity.sluzby.audit_knowledge_service as knowledge_module
import moduly.audity.sluzby.audit_knowledge_validator as validator_module

importlib.reload(validator_module)
importlib.reload(knowledge_module)
importlib.reload(editor_module)

from core.services.editable_catalog_service import editable_catalog_service
from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_knowledge_validator import (
    normalize_legacy_knowledge_data,
    validate_knowledge_data,
)

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_ASSERTION_ID = "vsechny_urazy_evidovany"


class AuditFieldOffice4TestCase(unittest.TestCase):
    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        bundled = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        shutil.copy2(bundled, self._path)
        self._make_legacy_assertions()
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _make_legacy_assertions(self) -> None:
        """Simuluje starší uživatelská data: tvrzení bez popisu / verification_type."""
        with self._path.open(encoding="utf-8") as handle:
            data = json.load(handle)

        for section in data.get("sekce") or []:
            if section.get("id") != _SECTION_ID:
                continue
            for index, item in enumerate(section.get("auditni_tvrzeni") or []):
                if not isinstance(item, dict):
                    continue
                # První dvě bez popisu (typický legacy stav).
                if index < 2:
                    item.pop("popis", None)
                item.pop("verification_type", None)
                if index == 0:
                    item["extra_meta"] = "keep-me"
            break

        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read(self) -> dict:
        with self._path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _section_assertions(self) -> list[dict]:
        for section in self._read().get("sekce") or []:
            if section.get("id") == _SECTION_ID:
                return [
                    item
                    for item in (section.get("auditni_tvrzeni") or [])
                    if isinstance(item, dict)
                ]
        self.fail(f"Section {_SECTION_ID} not found")

    def _assertion(self, assertion_id: str) -> dict:
        for item in self._section_assertions():
            if item.get("id") == assertion_id:
                return item
        self.fail(f"Assertion {assertion_id} not found")

    def _sibling_with_popis(self) -> dict:
        for item in self._section_assertions():
            if item.get("id") != _ASSERTION_ID and "popis" in item:
                return item
        self.fail("No sibling with popis found")

    def _save_type(self, verification_type: str) -> list[str]:
        item = self._assertion(_ASSERTION_ID)
        return audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            {
                "id": _ASSERTION_ID,
                "text": item.get("text") or item.get("nazev") or "",
                "popis": item.get("popis") or "",
                "zavaznost": item.get("zavaznost") or "stredni",
                "verification_type": verification_type,
                "poradi": item.get("poradi") or 10,
                "aktivni": bool(item.get("aktivni", True)),
            },
            assertion_id=_ASSERTION_ID,
        )

    def test_a_legacy_without_popis_validates_after_normalize(self) -> None:
        data = self._read()
        first = next(
            item
            for section in data["sekce"]
            if section.get("id") == _SECTION_ID
            for item in section["auditni_tvrzeni"]
            if item.get("id") == _ASSERTION_ID
        )
        self.assertNotIn("popis", first)
        errors = validate_knowledge_data(data, source_name=self._path.name)
        self.assertEqual(errors, [])
        self.assertEqual(first["popis"], "")

    def test_b_documentation_to_terrain_saves(self) -> None:
        self.assertNotIn("popis", self._assertion(_ASSERTION_ID))
        errors = self._save_type(VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(errors, [])
        self.assertEqual(
            self._assertion(_ASSERTION_ID)["verification_type"],
            VERIFICATION_TYPE_TERRAIN,
        )

    def test_c_terrain_to_documentation_saves(self) -> None:
        self.assertEqual(self._save_type(VERIFICATION_TYPE_TERRAIN), [])
        errors = self._save_type(VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(errors, [])
        self.assertEqual(
            self._assertion(_ASSERTION_ID)["verification_type"],
            VERIFICATION_TYPE_DOCUMENTATION,
        )

    def test_d_change_persists_after_reload(self) -> None:
        self.assertEqual(self._save_type(VERIFICATION_TYPE_TERRAIN), [])
        audit_knowledge_service.ensure_catalogs()
        criterion = audit_knowledge_service.get_criterion(
            _PROCESS_ID, _SECTION_ID, ensure=False
        )
        assert criterion is not None
        item = next(
            x
            for x in criterion.get("auditni_tvrzeni") or []
            if x.get("id") == _ASSERTION_ID
        )
        self.assertEqual(
            audit_knowledge_service.normalize_verification_type(
                item.get("verification_type")
            ),
            VERIFICATION_TYPE_TERRAIN,
        )

    def test_e_existing_popis_unchanged(self) -> None:
        sibling = self._sibling_with_popis()
        expected_popis = sibling["popis"]
        sibling_id = sibling["id"]
        self.assertEqual(self._save_type(VERIFICATION_TYPE_TERRAIN), [])
        self.assertEqual(self._assertion(sibling_id)["popis"], expected_popis)

    def test_f_missing_popis_normalized_to_empty(self) -> None:
        data = self._read()
        normalize_legacy_knowledge_data(data)
        legacy_items = [
            item
            for section in data["sekce"]
            if section.get("id") == _SECTION_ID
            for index, item in enumerate(section["auditni_tvrzeni"])
            if index < 2
        ]
        for item in legacy_items:
            self.assertEqual(item["popis"], "")

        self.assertEqual(self._save_type(VERIFICATION_TYPE_TERRAIN), [])
        # Po uložení je chybějící popis bezpečně zapsán jako prázdný řetězec.
        self.assertEqual(self._assertion(_ASSERTION_ID).get("popis"), "")

    def test_g_other_fields_preserved(self) -> None:
        before = self._assertion(_ASSERTION_ID)
        snapshot = {
            "id": before.get("id"),
            "text": before.get("text"),
            "zavaznost": before.get("zavaznost"),
            "poradi": before.get("poradi"),
            "aktivni": before.get("aktivni", True),
            "extra_meta": before.get("extra_meta"),
        }
        sibling = self._sibling_with_popis()
        sibling_snapshot = {
            "id": sibling["id"],
            "text": sibling.get("text"),
            "popis": sibling.get("popis"),
            "zavaznost": sibling.get("zavaznost"),
            "poradi": sibling.get("poradi"),
            "aktivni": sibling.get("aktivni", True),
        }

        self.assertEqual(self._save_type(VERIFICATION_TYPE_TERRAIN), [])
        after = self._assertion(_ASSERTION_ID)
        for key, value in snapshot.items():
            self.assertEqual(after.get(key), value)
        self.assertEqual(after["verification_type"], VERIFICATION_TYPE_TERRAIN)

        after_sibling = self._assertion(sibling_snapshot["id"])
        for key, value in sibling_snapshot.items():
            self.assertEqual(after_sibling.get(key), value)

    def test_h_existing_methodologies_remain_valid(self) -> None:
        bundled = editable_catalog_service.bundled_dir() / "audity"
        for path in sorted(bundled.glob("*.json")):
            if path.name == "procesy.json" or path.name.startswith("_"):
                continue
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            errors = validate_knowledge_data(data, source_name=path.name)
            self.assertEqual(errors, [], msg=f"{path.name}: {errors[:3]}")

    def test_normalize_preserves_existing_values(self) -> None:
        data = self._read()
        sibling_before = None
        for section in data["sekce"]:
            if section.get("id") != _SECTION_ID:
                continue
            for item in section["auditni_tvrzeni"]:
                if "popis" in item:
                    sibling_before = dict(item)
                    break
        assert sibling_before is not None
        expected_popis = sibling_before["popis"]

        normalize_legacy_knowledge_data(data)
        target = None
        sibling_after = None
        for section in data["sekce"]:
            if section.get("id") != _SECTION_ID:
                continue
            for item in section["auditni_tvrzeni"]:
                if item.get("id") == _ASSERTION_ID:
                    target = item
                if item.get("id") == sibling_before["id"]:
                    sibling_after = item

        assert target is not None and sibling_after is not None
        self.assertEqual(target["popis"], "")
        self.assertEqual(target["verification_type"], VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(target.get("extra_meta"), "keep-me")
        self.assertEqual(sibling_after["popis"], expected_popis)


if __name__ == "__main__":
    unittest.main()
