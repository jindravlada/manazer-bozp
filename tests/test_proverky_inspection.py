import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


class ProverkyInspectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def test_create_and_reload_inspection(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            title="Test prověrky",
        )
        loaded = bozp_inspection_service.get_by_id(inspection.id)

        assert loaded is not None
        self.assertEqual(loaded.title, "Test prověrky")
        self.assertTrue(loaded.number)

    def test_update_inspection(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        updated = bozp_inspection_service.update_inspection(
            inspection.id,
            title="Upravená prověrka",
        )

        assert updated is not None
        self.assertEqual(updated.title, "Upravená prověrka")


if __name__ == "__main__":
    unittest.main()
