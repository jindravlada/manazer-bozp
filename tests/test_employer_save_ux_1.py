"""EMPLOYER-SAVE-UX-1: potvrzení uložení a ochrana neuložených změn."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employer-save-ux-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.services.ares_service import ares_service
    from core.services.cz_nace_service import cz_nace_service
    from core.windows.main_window import MainWindow
    from moduly.nastaveni.modely.employer import Employer
    from moduly.nastaveni.sluzby.settings_service import (
        SettingsEmployerError,
        settings_service,
    )
    from moduly.nastaveni.ui.employer_nace_choice_dialog import EmployerNaceChoiceDialog
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage

_DISPLAY = "49.20 \u2013 Kolejová nákladní doprava"
_PROMPT = "moduly.nastaveni.ui.nastaveni_page.confirm_unsaved_editor_close"
_CARGO_CODES = ["27510", "52100", "49200"]


def _parse(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    with patch(
        "core.services.ares_service.safe_https_get",
        return_value=SimpleNamespace(status_code=200, body=body, final_url="https://ares.gov.cz/x"),
    ):
        data = ares_service.find_by_ico(str(payload["ico"]))
    if data is None:
        raise AssertionError("parser nevrátil subjekt")
    return data


class EmployerSaveUx1TestCase(unittest.TestCase):
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
        self.employer_index = self.page.tabs.indexOf(self.page.employer_tab)

    def _open_employer_tab(self) -> None:
        self.page.tabs.setCurrentIndex(self.employer_index)
        self.assertEqual(self.page.tabs.currentIndex(), self.employer_index)

    def test_01_field_edit_marks_dirty(self) -> None:
        self.assertFalse(self.page.employer_has_unsaved_changes())
        self.page.employer_name.setText("Nový název")
        self.assertTrue(self.page.employer_has_unsaved_changes())

    def test_02_ares_load_marks_dirty(self) -> None:
        self.page.employer_ico.setText("12345678")
        data = _parse(
            {
                "ico": "12345678",
                "obchodniJmeno": "Nákladní doprava s.r.o.",
                "sidlo": {"nazevUlice": "Hlavní", "cisloDomovni": 1, "nazevObce": "Praha", "psc": 11000},
                "czNace": ["49200"],
            }
        )
        with patch.object(ares_service, "find_by_ico", return_value=data):
            with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "critical"):
                self.page.load_from_ares()

        self.assertEqual(self.page.employer_name.text(), "Nákladní doprava s.r.o.")
        self.assertTrue(self.page.employer_has_unsaved_changes())
        self.assertIsNone(settings_service.get_employer())

    def test_03_nace_selection_marks_dirty(self) -> None:
        index = self.page.employer_nace.findData("49.20")
        self.assertGreaterEqual(index, 0)
        self.page.employer_nace.setCurrentIndex(index)
        self.assertTrue(self.page.employer_has_unsaved_changes())
        self.assertEqual(self.page._stored_employer_nace(), "49.20")

    def test_04_successful_save_persists_and_clears_dirty(self) -> None:
        self.page.employer_ico.setText("12345678")
        self.page.employer_name.setText("Dopravce")
        self.page.employer_address.setText("Praha")
        index = self.page.employer_nace.findData("49.20")
        self.page.employer_nace.setCurrentIndex(index)

        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            self.assertTrue(self.page.save_employer())

        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.name, "Dopravce")
        self.assertEqual(employer.nace, "49.20")
        self.assertFalse(self.page.employer_has_unsaved_changes())

    def test_05_successful_save_shows_confirmation(self) -> None:
        self.page.employer_name.setText("Dopravce")
        with patch.object(QMessageBox, "warning") as warning:
            with patch.object(QMessageBox, "information") as info:
                self.assertTrue(self.page.save_employer())
        warning.assert_not_called()
        info.assert_called_once()
        self.assertEqual(info.call_args.args[1], "Zaměstnavatel")
        self.assertEqual(info.call_args.args[2], "Údaje zaměstnavatele byly uloženy.")

    def test_06_clean_leave_does_not_ask(self) -> None:
        self._open_employer_tab()
        with patch(_PROMPT) as prompt:
            self.page.tabs.setCurrentIndex(0)
        prompt.assert_not_called()
        self.assertEqual(self.page.tabs.currentIndex(), 0)

    def test_07_leave_save_persists_changes(self) -> None:
        self._open_employer_tab()
        self.page.employer_name.setText("Uložit při odchodu")
        self.page.employer_ico.setText("12345678")
        with patch(_PROMPT, return_value="save") as prompt:
            with patch.object(QMessageBox, "information") as info:
                with patch.object(QMessageBox, "warning"):
                    self.page.tabs.setCurrentIndex(0)
        prompt.assert_called_once()
        self.assertEqual(prompt.call_args.kwargs["title"], "Zaměstnavatel")
        info.assert_called_once()
        self.assertEqual(self.page.tabs.currentIndex(), 0)
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.name, "Uložit při odchodu")
        self.assertFalse(self.page.employer_has_unsaved_changes())

    def test_08_leave_discard_keeps_database(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Původní",
            address="Praha",
            nace="49.20",
        )
        self.page.refresh()
        self._open_employer_tab()
        self.page.employer_name.setText("Rozpracováno")
        with patch(_PROMPT, return_value="discard") as prompt:
            self.page.tabs.setCurrentIndex(0)
        prompt.assert_called_once()
        self.assertEqual(self.page.tabs.currentIndex(), 0)
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.name, "Původní")
        self.assertEqual(employer.nace, "49.20")
        self.assertEqual(self.page.employer_name.text(), "Původní")
        self.assertFalse(self.page.employer_has_unsaved_changes())

    def test_09_leave_cancel_keeps_the_form_open(self) -> None:
        self._open_employer_tab()
        self.page.employer_name.setText("Zůstat")
        with patch(_PROMPT, return_value="cancel") as prompt:
            self.page.tabs.setCurrentIndex(0)
        prompt.assert_called_once()
        self.assertEqual(self.page.tabs.currentIndex(), self.employer_index)
        self.assertEqual(self.page.employer_name.text(), "Zůstat")
        self.assertTrue(self.page.employer_has_unsaved_changes())
        self.assertIsNone(settings_service.get_employer())

    def test_10_ares_nace_leave_without_manual_save_prompts_and_can_save(self) -> None:
        self._open_employer_tab()
        self.page.employer_ico.setText("28196678")
        data = _parse(
            {
                "ico": "28196678",
                "obchodniJmeno": "ČD Cargo, a.s.",
                "sidlo": {
                    "nazevUlice": "Jankovcova",
                    "cisloDomovni": 1569,
                    "cisloOrientacni": "2",
                    "nazevObce": "Praha",
                    "psc": 17000,
                },
                "czNace2008": ["49200"],
                "czNace": _CARGO_CODES,
            }
        )

        def choose(dialog: EmployerNaceChoiceDialog) -> str:
            for row in range(dialog.activities.count()):
                item = dialog.activities.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == "49200":
                    dialog.activities.setCurrentRow(row)
                    return dialog.selected_code()
            raise AssertionError("49200 chybí ve výběru")

        with patch.object(ares_service, "find_by_ico", return_value=data):
            with patch.object(EmployerNaceChoiceDialog, "choose", choose):
                with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "critical"):
                    self.page.load_from_ares()

        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertTrue(self.page.employer_has_unsaved_changes())
        self.assertIsNone(settings_service.get_employer())

        with patch(_PROMPT, return_value="save") as prompt:
            with patch.object(QMessageBox, "information"):
                with patch.object(QMessageBox, "warning"):
                    self.page.tabs.setCurrentIndex(0)
        prompt.assert_called_once()
        self.assertEqual(self.page.tabs.currentIndex(), 0)

        self.page.refresh()
        self._open_employer_tab()
        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")
        self.assertFalse(self.page.employer_has_unsaved_changes())
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.name, "ČD Cargo, a.s.")
        self.assertEqual(employer.nace, "49.20")
        self.assertEqual(cz_nace_service.get_display(employer.nace), _DISPLAY)

    def test_failed_save_shows_no_success_and_blocks_leave(self) -> None:
        self._open_employer_tab()
        self.page.employer_name.setText("Neuložitelné")
        with patch.object(
            settings_service,
            "save_employer",
            side_effect=SettingsEmployerError("nelze uložit"),
        ):
            with patch.object(QMessageBox, "warning") as warning:
                with patch.object(QMessageBox, "information") as info:
                    with patch(_PROMPT, return_value="save"):
                        self.page.tabs.setCurrentIndex(0)
        warning.assert_called_once()
        info.assert_not_called()
        self.assertEqual(self.page.tabs.currentIndex(), self.employer_index)
        self.assertEqual(self.page.employer_name.text(), "Neuložitelné")
        self.assertTrue(self.page.employer_has_unsaved_changes())
        self.assertIsNone(settings_service.get_employer())

    def test_module_switch_and_window_close_honor_the_guard(self) -> None:
        window = MainWindow()
        page = window._page_widgets["nastaveni"]
        try:
            window._show("nastaveni")
            self.assertIs(window.current_page_widget(), page)
            page.employer_name.setText("Neuloženo v modulu")
            with patch.object(page, "confirm_leave_employer_edit", return_value=False) as guard:
                window._show("dashboard")
                self.assertIs(window.current_page_widget(), page)
                event = QCloseEvent()
                window.closeEvent(event)
                self.assertFalse(event.isAccepted())
                self.assertGreaterEqual(guard.call_count, 2)
            with patch.object(page, "confirm_leave_employer_edit", return_value=True):
                window._show("dashboard")
            self.assertIs(window.current_page_widget(), window._page_widgets["dashboard"])
        finally:
            page._capture_employer_baseline()
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
