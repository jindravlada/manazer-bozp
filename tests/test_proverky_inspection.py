import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
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
    from moduly.nastaveni.sluzby.settings_service import settings_service


class ProverkyInspectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

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

    def test_spis_widget_sections(self) -> None:
        from PySide6.QtWidgets import QGroupBox

        from moduly.proverky.ui.bozp_inspection_spis_widget import BozpInspectionSpisWidget

        widget = BozpInspectionSpisWidget()
        section_titles = {box.title() for box in widget.findChildren(QGroupBox)}

        self.assertEqual(
            section_titles,
            {"Základní údaje", "Termíny", "Typ prověrky"},
        )
        self.assertFalse(hasattr(widget, "number_header"))

    def test_spis_widget_load_and_get_data(self) -> None:
        from moduly.proverky.constants import DEFAULT_INSPECTION_TYPE
        from moduly.proverky.ui.bozp_inspection_spis_widget import BozpInspectionSpisWidget

        workplace = settings_service.save_workplace(name="Hala A")
        inspection = SimpleNamespace(
            number="2026/001",
            inspection_type=DEFAULT_INSPECTION_TYPE,
            year=2026,
            planned_month=3,
            inspection_date=date(2026, 3, 15),
            started_at=date(2026, 3, 10),
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )

        widget = BozpInspectionSpisWidget()
        widget.load_inspection(inspection)
        data = widget.get_data()

        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["planned_month"], 3)
        self.assertEqual(data["inspection_date"], date(2026, 3, 15))
        self.assertEqual(data["started_at"], date(2026, 3, 10))
        self.assertEqual(data["inspection_type"], DEFAULT_INSPECTION_TYPE)
        self.assertEqual(data["workplace_id"], workplace.id)
        self.assertNotIn("status", data)
        self.assertNotIn("finished_at", data)

    def test_spis_fields_save_and_reload(self) -> None:
        workplace = settings_service.save_workplace(name="Sklad B")
        inspection = bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=5,
            inspection_date=date(2026, 5, 12),
            started_at=date(2026, 5, 10),
            finished_at=date(2026, 5, 14),
            inspection_type="Mimořádná",
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )

        loaded = bozp_inspection_service.get_by_id(inspection.id)

        assert loaded is not None
        self.assertEqual(loaded.year, 2026)
        self.assertEqual(loaded.planned_month, 5)
        self.assertEqual(loaded.inspection_date, date(2026, 5, 12))
        self.assertEqual(loaded.started_at, date(2026, 5, 10))
        self.assertEqual(loaded.finished_at, date(2026, 5, 14))
        self.assertEqual(loaded.status, "Dokončeno")
        self.assertEqual(loaded.inspection_type, "Mimořádná")
        self.assertEqual(loaded.workplace_id, workplace.id)
        self.assertEqual(loaded.workplace_name, workplace.name)


if __name__ == "__main__":
    unittest.main()
