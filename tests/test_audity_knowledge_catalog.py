import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_knowledge_validator import (
        default_audity_dir,
        validate_all_catalogs,
    )


class AudityKnowledgeCatalogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_all_catalog_json_files_are_valid(self) -> None:
        errors = validate_all_catalogs(default_audity_dir())
        self.assertEqual(errors, [])

    def test_each_registered_process_loads_independently(self) -> None:
        processes = audit_knowledge_service.get_processes(include_inactive=True)

        self.assertGreaterEqual(len(processes), 1)
        for process in processes:
            with self.subTest(process_id=process.id):
                self.assertTrue(process.has_knowledge_file)
                knowledge = audit_knowledge_service.load_process_knowledge(process)
                self.assertIsNotNone(knowledge)
                assert knowledge is not None
                self.assertEqual(knowledge["id"], process.id)
                self.assertIsInstance(knowledge.get("sekce"), list)

    def test_template_is_not_registered_in_catalog(self) -> None:
        processes = audit_knowledge_service.get_processes(include_inactive=True)
        process_ids = {process.id for process in processes}
        self.assertNotIn("ID_PROCESU", process_ids)


if __name__ == "__main__":
    unittest.main()
