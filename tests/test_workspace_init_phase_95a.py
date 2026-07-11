"""Fáze 95a – inicializace výchozích dat při čisté instalaci / poškozeném workspace."""

from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class WorkspaceInitPhase95aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp())
        self._home_patcher = patch.object(Path, "home", return_value=self._tmp)
        self._home_patcher.start()

        import core.services.editable_catalog_service as catalog_module

        importlib.reload(catalog_module)
        self.catalog_module = catalog_module

        import core.services.storage_service as storage_module

        importlib.reload(storage_module)
        self.storage_module = storage_module
        self.storage = storage_module.storage_service

        from moduly.audity.sluzby import audit_knowledge_service as aks_module

        importlib.reload(aks_module)
        self.aks_module = aks_module
        self.audit_knowledge_service = aks_module.audit_knowledge_service

    def tearDown(self) -> None:
        self._home_patcher.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_ensure_structure_creates_required_directories(self) -> None:
        expected = [
            "databaze",
            "ciselniky",
            "konfigurace",
            "prilohy",
            "control_results",
            "export",
            "import",
            "zalohy",
            "templates",
            "logy",
        ]
        for name in expected:
            with self.subTest(directory=name):
                self.assertTrue((self.storage.base / name).is_dir())

    def test_ensure_structure_copies_procesy_json(self) -> None:
        procesy = self.storage.ciselniky_dir / "audity" / "procesy.json"
        self.assertTrue(procesy.is_file(), f"Chybí {procesy}")

        bundled = PROJECT_ROOT / "ciselniky" / "audity" / "procesy.json"
        self.assertEqual(procesy.read_bytes(), bundled.read_bytes())

    def test_ensure_structure_copies_audit_and_proverky_methodologies(self) -> None:
        self.assertTrue((self.storage.ciselniky_dir / "audity" / "rizeni_rizik.json").is_file())
        self.assertTrue((self.storage.ciselniky_dir / "proverky" / "oblasti.json").is_file())
        self.assertTrue((self.storage.ciselniky_dir / "proverky" / "bozp_obecne.json").is_file())
        self.assertTrue(
            (self.storage.ciselniky_dir / "modulove" / "vysetrovani_mu" / "ishikawa_faktory.json").is_file()
        )

    def test_existing_user_file_is_not_overwritten(self) -> None:
        procesy = self.storage.ciselniky_dir / "audity" / "procesy.json"
        marker = '{"procesy": [], "custom": true}\n'
        procesy.write_text(marker, encoding="utf-8")

        self.storage.ensure_structure()

        self.assertEqual(procesy.read_text(encoding="utf-8"), marker)

    def test_missing_file_is_restored_on_next_start(self) -> None:
        procesy = self.storage.ciselniky_dir / "audity" / "procesy.json"
        procesy.unlink()
        self.assertFalse(procesy.exists())

        self.storage.ensure_structure()

        self.assertTrue(procesy.is_file())
        bundled = PROJECT_ROOT / "ciselniky" / "audity" / "procesy.json"
        self.assertEqual(procesy.read_bytes(), bundled.read_bytes())

    def test_get_processes_works_after_clean_init(self) -> None:
        processes = self.audit_knowledge_service.get_processes()
        self.assertGreaterEqual(len(processes), 1)

    def test_missing_procesy_raises_audit_catalog_error(self) -> None:
        procesy = self.storage.ciselniky_dir / "audity" / "procesy.json"
        procesy.unlink()

        empty_bundled = self._tmp / "empty_bundle"
        empty_bundled.mkdir()
        with patch.object(
            self.catalog_module.editable_catalog_service,
            "bundled_dir",
            return_value=empty_bundled,
        ):
            with self.assertRaises(self.aks_module.AuditCatalogError) as ctx:
                self.audit_knowledge_service.get_processes()

        self.assertIn("procesy.json", str(ctx.exception))

    def test_tree_widget_survives_missing_catalog(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        procesy = self.storage.ciselniky_dir / "audity" / "procesy.json"
        procesy.unlink()

        empty_bundled = self._tmp / "empty_bundle_ui"
        empty_bundled.mkdir()

        from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget

        with patch.object(
            self.catalog_module.editable_catalog_service,
            "bundled_dir",
            return_value=empty_bundled,
        ):
            widget = AuditKnowledgeTreeWidget()
            widget.reload_tree()

        self.assertEqual(widget.topLevelItemCount(), 0)
        self.assertIsNotNone(widget.catalog_error_message)
        self.assertIn("procesy.json", widget.catalog_error_message or "")

    def test_build_scripts_package_ciselniky(self) -> None:
        for script_name in ("build_release.sh", "build_old_release.sh"):
            content = (PROJECT_ROOT / script_name).read_text(encoding="utf-8")
            with self.subTest(script=script_name):
                self.assertIn("ciselniky:ciselniky", content)
                self.assertIn("zdroje:zdroje", content)

        spec = (PROJECT_ROOT / "ManazerBOZP.spec").read_text(encoding="utf-8")
        self.assertIn("('ciselniky', 'ciselniky')", spec)
        self.assertIn("('zdroje', 'zdroje')", spec)

    def test_project_root_uses_meipass_when_frozen(self) -> None:
        from core.paths import project_root

        fake = self._tmp / "meipass"
        fake.mkdir()
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", str(fake), create=True):
                self.assertEqual(project_root(), fake)


if __name__ == "__main__":
    unittest.main()
