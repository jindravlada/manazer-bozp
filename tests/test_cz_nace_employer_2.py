"""CZ-NACE-2: hlavní CZ-NACE zaměstnavatele ukládá kód a v UI ukazuje název."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="cz-nace-employer-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.services.ares_service import ares_service
    from core.services.cz_nace_service import CzNaceService
    from moduly.nastaveni.modely.employer import Employer
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage

_DISPLAY = "49.20 \u2013 Kolejová nákladní doprava"


class CzNaceEmployer2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Employer))
            session.commit()
        self.page = NastaveniPage()

    def test_stored_code_shows_code_and_name(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Dopravce",
            address="Praha",
            nace="49.20",
        )
        self.page.refresh()

        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page._stored_employer_nace(), "49.20")

    def test_ares_code_selects_catalog_item_and_keeps_full_list(self) -> None:
        catalog_count = self.page.employer_nace.count()
        self.assertGreater(catalog_count, 1000)
        self.page.employer_ico.setText("12345678")

        with patch.object(
            ares_service,
            "find_by_ico",
            return_value={
                "ico": "12345678",
                "name": "Nákladní doprava s.r.o.",
                "address": "Praha",
                "nace_code": "49200",
                "nace": "49200",
                "nace_list": ["49200"],
            },
        ):
            with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "critical"):
                self.page.load_from_ares()

        self.assertEqual(self.page.employer_nace.count(), catalog_count)
        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")
        self.assertGreater(
            self.page.employer_nace.findData("62.10"),
            -1,
        )

    def test_selected_item_saves_only_code(self) -> None:
        index = self.page.employer_nace.findData("49.20")
        self.assertGreaterEqual(index, 0)
        self.page.employer_nace.setCurrentIndex(index)
        self.page.employer_name.setText("Dopravce")
        self.page.employer_ico.setText("12345678")

        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            self.page.save_employer()

        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "49.20")
        self.assertNotIn("Kolejová", employer.nace)

    def test_historical_label_loads_and_saves_as_code(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Dopravce",
            address="Praha",
            nace=_DISPLAY,
        )
        self.page.refresh()
        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")

        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            self.page.save_employer()

        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "49.20")

    def test_unknown_code_stays_visible_and_is_not_dropped(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Stará firma",
            address="Praha",
            nace="62010",
        )
        catalog_count = self.page.employer_nace.count()
        self.page.refresh()

        self.assertEqual(self.page.employer_nace.currentText(), "62010")
        self.assertEqual(self.page.employer_nace.count(), catalog_count)
        self.assertEqual(self.page._stored_employer_nace(), "62010")

        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            self.page.save_employer()

        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "62010")

    def test_bundled_catalog_path_ignores_working_directory(self) -> None:
        previous = os.getcwd()
        os.chdir(tempfile.gettempdir())
        try:
            service = CzNaceService()
            self.assertTrue(service.file_path.is_absolute())
            self.assertTrue(service.file_path.is_file())
            self.assertEqual(service.file_path.name, "cz_nace.json")
            code, display = service.resolve("49200")
        finally:
            os.chdir(previous)

        self.assertEqual(code, "49.20")
        self.assertEqual(display, _DISPLAY)


if __name__ == "__main__":
    unittest.main()
