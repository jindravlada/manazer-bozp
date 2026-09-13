"""SEC-02a: soubor_znalosti nesmí opustit adresář metodiky."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.services.editable_catalog_service import editable_catalog_service
from core.utils.confined_path import resolve_confined_path
from moduly.audity.sluzby.audit_knowledge_service import (
    AuditKnowledgeService,
    AuditProcessDefinition,
    audit_knowledge_service,
)
from moduly.proverky.sluzby.proverky_knowledge_service import (
    InspectionAreaDefinition,
    ProverkyKnowledgeService,
    proverky_knowledge_service,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


class ResolveConfinedPathTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.audity = self.root / "ciselniky" / "audity"
        self.audity.mkdir(parents=True)
        (self.audity / "planovani_bozp.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    def test_ordinary_relative_path_stays_inside(self) -> None:
        resolved = resolve_confined_path(self.audity, "planovani_bozp.json")
        self.assertEqual(resolved, (self.audity / "planovani_bozp.json").resolve())

    def test_parent_escape_is_rejected(self) -> None:
        self.assertIsNone(resolve_confined_path(self.audity, "../secret.json"))
        self.assertIsNone(resolve_confined_path(self.audity, "../../databaze/manager_bozp.db"))

    def test_absolute_path_is_rejected(self) -> None:
        target = (self.root / "outside.json").resolve()
        self.assertIsNone(resolve_confined_path(self.audity, str(target)))

    def test_nested_relative_stays_inside(self) -> None:
        nested = self.audity / "podadresar" / "soubor.json"
        nested.parent.mkdir(parents=True)
        nested.write_text("{}\n", encoding="utf-8")
        resolved = resolve_confined_path(self.audity, "podadresar/soubor.json")
        self.assertEqual(resolved, nested.resolve())


class AuditKnowledgePathTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.audity = self.root / "ciselniky" / "audity"
        self.audity.mkdir(parents=True)
        self.db_dir = self.root / "databaze"
        self.db_dir.mkdir()
        self.db_file = self.db_dir / "manager_bozp.db"
        self.db_file.write_bytes(b"ORIGINAL-DB")
        self._payload = {"id": "sec02a", "nazev": "test"}
        _write_json(self.audity / "planovani_bozp.json", self._payload)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    def _process(self, soubor: str) -> AuditProcessDefinition:
        return AuditProcessDefinition(
            id="sec02a",
            nazev="SEC-02a",
            popis="",
            ucel_procesu="",
            poradi=1,
            aktivni=True,
            soubor_znalosti=soubor,
        )

    def _patch_audity(self):
        audity = self.audity
        return patch.object(
            AuditKnowledgeService,
            "audity_dir",
            property(lambda _self: audity),
        )

    def test_ordinary_relative_path_loads_and_saves(self) -> None:
        process = self._process("planovani_bozp.json")
        with self._patch_audity():
            loaded = audit_knowledge_service.load_process_knowledge(process, ensure=False)
            self.assertEqual(loaded, self._payload)
            saved = audit_knowledge_service._save_knowledge(
                process,
                {"id": "sec02a", "nazev": "ulozeno"},
            )
        self.assertTrue(saved)
        stored = json.loads((self.audity / "planovani_bozp.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["nazev"], "ulozeno")
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")

    def test_parent_escape_is_rejected(self) -> None:
        secret = self.root / "ciselniky" / "tajne.json"
        _write_json(secret, {"stolen": True})
        process = self._process("../tajne.json")
        with self._patch_audity():
            self.assertIsNone(
                audit_knowledge_service.load_process_knowledge(process, ensure=False)
            )
            self.assertFalse(
                audit_knowledge_service._save_knowledge(process, {"id": "evil"})
            )
        self.assertNotIn("evil", secret.read_text(encoding="utf-8"))

    def test_absolute_path_is_rejected(self) -> None:
        process = self._process(str(self.db_file.resolve()))
        with self._patch_audity():
            self.assertIsNone(
                audit_knowledge_service.load_process_knowledge(process, ensure=False)
            )
            self.assertFalse(
                audit_knowledge_service._save_knowledge(process, {"id": "evil"})
            )
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")

    def test_database_file_is_not_written(self) -> None:
        process = self._process("../../databaze/manager_bozp.db")
        with self._patch_audity():
            self.assertFalse(
                audit_knowledge_service._save_knowledge(process, {"id": "evil-db"})
            )
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")
        self.assertFalse((self.audity / "manager_bozp.db").exists())


class ProverkyKnowledgePathTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.proverky = self.root / "ciselniky" / "proverky"
        self.proverky.mkdir(parents=True)
        self.db_dir = self.root / "databaze"
        self.db_dir.mkdir()
        self.db_file = self.db_dir / "manager_bozp.db"
        self.db_file.write_bytes(b"ORIGINAL-DB")
        self._payload = {"id": "bozp_obecne", "nazev": "test"}
        _write_json(self.proverky / "bozp_obecne.json", self._payload)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    def _area(self, soubor: str) -> InspectionAreaDefinition:
        return InspectionAreaDefinition(
            id="bozp_obecne",
            nazev="SEC-02a",
            popis="",
            poradi=1,
            aktivni=True,
            soubor_znalosti=soubor,
        )

    def _patch_proverky(self):
        proverky = self.proverky
        return patch.object(
            ProverkyKnowledgeService,
            "proverky_dir",
            property(lambda _self: proverky),
        )

    def test_ordinary_relative_path_loads_and_saves(self) -> None:
        area = self._area("bozp_obecne.json")
        with self._patch_proverky():
            loaded = proverky_knowledge_service.load_area_knowledge(area, ensure=False)
            self.assertEqual(loaded, self._payload)
            saved = proverky_knowledge_service._save_knowledge(
                area,
                {"id": "bozp_obecne", "nazev": "ulozeno"},
            )
        self.assertTrue(saved)
        stored = json.loads((self.proverky / "bozp_obecne.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["nazev"], "ulozeno")
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")

    def test_parent_escape_is_rejected(self) -> None:
        secret = self.root / "ciselniky" / "tajne.json"
        _write_json(secret, {"stolen": True})
        area = self._area("../tajne.json")
        with self._patch_proverky():
            self.assertIsNone(
                proverky_knowledge_service.load_area_knowledge(area, ensure=False)
            )
            self.assertFalse(
                proverky_knowledge_service._save_knowledge(area, {"id": "evil"})
            )
        self.assertNotIn("evil", secret.read_text(encoding="utf-8"))

    def test_absolute_path_is_rejected(self) -> None:
        area = self._area(str(self.db_file.resolve()))
        with self._patch_proverky():
            self.assertIsNone(
                proverky_knowledge_service.load_area_knowledge(area, ensure=False)
            )
            self.assertFalse(
                proverky_knowledge_service._save_knowledge(area, {"id": "evil"})
            )
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")

    def test_database_file_is_not_written(self) -> None:
        area = self._area("../../databaze/manager_bozp.db")
        with self._patch_proverky():
            self.assertFalse(
                proverky_knowledge_service._save_knowledge(area, {"id": "evil-db"})
            )
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")


class EditableCatalogConfineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.ciselniky = self.root / "ciselniky"
        self.ciselniky.mkdir()
        self.db_file = self.root / "databaze" / "manager_bozp.db"
        self.db_file.parent.mkdir()
        self.db_file.write_bytes(b"ORIGINAL-DB")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    def test_ensure_catalog_rejects_database_escape(self) -> None:
        with self.assertRaises(ValueError):
            editable_catalog_service.ensure_catalog(
                self.ciselniky,
                "audity/../../databaze/manager_bozp.db",
            )
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")

    def test_ensure_catalog_accepts_ordinary_relative_path(self) -> None:
        target = editable_catalog_service.ensure_catalog(
            self.ciselniky,
            "audity/planovani_bozp.json",
        )
        self.assertTrue(str(target).startswith(str(self.ciselniky.resolve())))
        self.assertEqual(target.name, "planovani_bozp.json")
        self.assertEqual(self.db_file.read_bytes(), b"ORIGINAL-DB")
