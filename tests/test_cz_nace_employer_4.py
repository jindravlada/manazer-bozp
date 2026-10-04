"""CZ-NACE-4: ARES nenastaví první kód jako hlavní činnost."""

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

_TMP = Path(tempfile.mkdtemp(prefix="cz-nace-employer-4-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.services.ares_service import ares_service
    from core.services.cz_nace_service import cz_nace_service
    from moduly.nastaveni.modely.employer import Employer
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.ui.employer_nace_choice_dialog import EmployerNaceChoiceDialog
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage

_DISPLAY = "49.20 \u2013 Kolejová nákladní doprava"
_CARGO_CODES = ["27510", "52100", "772", "49200", "49410"]
_HOUSEHOLD = "27.51"


def _payload(ico: str, cz_nace: list[str], *, cz_nace_2008: list[str] | None = None) -> dict:
    payload = {
        "ico": ico,
        "obchodniJmeno": "Zkušební subjekt a.s.",
        "sidlo": {
            "nazevUlice": "Jankovcova",
            "cisloDomovni": 1569,
            "cisloOrientacni": "2",
            "nazevObce": "Praha",
            "psc": 17000,
        },
        "czNace": cz_nace,
    }
    if cz_nace_2008 is not None:
        payload["czNace2008"] = cz_nace_2008
    return payload


def _parse(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    with patch(
        "core.services.ares_service.safe_https_get",
        return_value=SimpleNamespace(
            status_code=200,
            body=body,
            final_url="https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/1",
        ),
    ):
        data = ares_service.find_by_ico(str(payload["ico"]))
    if data is None:
        raise AssertionError("parser nevrátil subjekt")
    return data


class CzNaceEmployer4TestCase(unittest.TestCase):
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
        self.catalog_count = self.page.employer_nace.count()
        self.assertGreater(self.catalog_count, 1000)

    def _load(self, payload: dict, choose=None) -> dict:
        data = _parse(payload)
        self.page.employer_ico.setText(str(payload["ico"]))
        with patch.object(ares_service, "find_by_ico", return_value=data):
            if choose is None:
                self.page.load_from_ares()
            else:
                with patch.object(EmployerNaceChoiceDialog, "choose", choose):
                    self.page.load_from_ares()
        return data

    def _save(self) -> None:
        with patch.object(QMessageBox, "warning"):
            self.page.save_employer()

    def test_a_single_code_is_applied_without_dialog(self) -> None:
        def choose(_dialog):
            raise AssertionError("dialog se při jednom kódu nesmí otevřít")

        data = self._load(
            _payload("12345678", ["49200"], cz_nace_2008=["27510"]),
            choose=choose,
        )

        self.assertEqual(data["nace_codes"], ["49200"])
        self.assertEqual(data["nace_code"], "49200")
        self.assertEqual(data["nace"], _DISPLAY)
        self.assertNotIn("27510", data["nace_codes"])
        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")
        self.assertEqual(self.page.employer_nace.count(), self.catalog_count)

        self._save()
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "49.20")

    def test_b_multiple_codes_do_not_select_the_first(self) -> None:
        seen: dict[str, object] = {}

        def choose(dialog: EmployerNaceChoiceDialog):
            seen["row"] = dialog.activities.currentRow()
            seen["ok"] = dialog.ok_button.isEnabled() if dialog.ok_button else None
            seen["during"] = self.page.employer_nace.currentText()
            return None

        data = self._load(_payload("27082440", ["33140", "49410"]), choose=choose)

        self.assertEqual(data["nace_codes"], ["33140", "49410"])
        self.assertEqual(data["nace_code"], "")
        self.assertEqual(data["nace"], "")
        self.assertEqual(seen["row"], -1)
        self.assertIs(seen["ok"], False)
        self.assertNotIn("33.14", str(seen["during"]))
        self.assertEqual(self.page.employer_nace.currentIndex(), -1)
        self.assertEqual(self.page.employer_nace.currentText(), "")
        self.assertEqual(self.page.employer_name.text(), "Zkušební subjekt a.s.")

    def test_c_cargo_fixture_does_not_mark_household_appliances_as_main(self) -> None:
        seen: dict[str, object] = {}

        def choose(dialog: EmployerNaceChoiceDialog):
            seen["first"] = dialog.activities.item(0).text()
            seen["row"] = dialog.activities.currentRow()
            return None

        data = self._load(
            _payload(
                "28196678",
                _CARGO_CODES,
                cz_nace_2008=["49200", "16230"],
            ),
            choose=choose,
        )

        self.assertEqual(data["nace_codes"], _CARGO_CODES)
        self.assertEqual(data["nace_codes"][0], "27510")
        self.assertIn("49200", data["nace_codes"])
        self.assertNotEqual(data["nace_codes"][0], "49200")
        self.assertEqual(data["nace_code"], "")
        self.assertNotIn("16230", data["nace_codes"])
        displays = [cz_nace_service.get_display(code) for code in _CARGO_CODES]
        self.assertEqual(data["nace_list"], displays)
        self.assertEqual(seen["first"], cz_nace_service.get_display("27510"))
        self.assertEqual(seen["row"], -1)
        self.assertNotEqual(self.page.employer_nace.currentData(), _HOUSEHOLD)
        self.assertNotIn(_HOUSEHOLD, self.page.employer_nace.currentText())
        self.assertEqual(self.page.employer_nace.count(), self.catalog_count)

    def test_d_existing_code_is_preselected_in_the_dialog(self) -> None:
        settings_service.save_employer(
            ico="28196678",
            name="ČD Cargo, a.s.",
            address="Praha",
            nace="49.20",
        )
        self.page.refresh()
        seen: dict[str, object] = {}

        def choose(dialog: EmployerNaceChoiceDialog):
            seen["code"] = dialog.selected_code()
            seen["row"] = dialog.activities.currentRow()
            return None

        self._load(
            _payload("28196678", _CARGO_CODES, cz_nace_2008=["49200"]),
            choose=choose,
        )

        self.assertEqual(seen["code"], "49200")
        self.assertNotEqual(seen["row"], 0)
        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")

    def test_e_user_choice_sets_display_and_saves_code(self) -> None:
        def choose(dialog: EmployerNaceChoiceDialog):
            for row in range(dialog.activities.count()):
                item = dialog.activities.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == "49200":
                    dialog.activities.setCurrentRow(row)
                    return dialog.selected_code()
            raise AssertionError("49200 chybí ve výběru")

        self._load(
            _payload("28196678", _CARGO_CODES, cz_nace_2008=["27510"]),
            choose=choose,
        )

        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")
        self.assertEqual(self.page.employer_nace.count(), self.catalog_count)
        self.assertGreater(self.page.employer_nace.findData("62.10"), -1)

        self._save()
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "49.20")

    def test_f_cancel_keeps_existing_value(self) -> None:
        settings_service.save_employer(
            ico="28196678",
            name="ČD Cargo, a.s.",
            address="Praha",
            nace="49.20",
        )
        self.page.refresh()

        self._load(
            _payload("28196678", _CARGO_CODES),
            choose=lambda _dialog: None,
        )

        self.assertEqual(self.page.employer_nace.currentText(), _DISPLAY)
        self.assertEqual(self.page.employer_nace.currentData(), "49.20")
        self._save()
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "49.20")

    def test_g_unknown_code_stays_visible_and_can_be_stored(self) -> None:
        seen: dict[str, object] = {}

        def choose(dialog: EmployerNaceChoiceDialog):
            texts = [
                dialog.activities.item(row).text()
                for row in range(dialog.activities.count())
            ]
            seen["texts"] = texts
            for row in range(dialog.activities.count()):
                item = dialog.activities.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == "99999":
                    dialog.activities.setCurrentRow(row)
                    return dialog.selected_code()
            raise AssertionError("99999 chybí ve výběru")

        self._load(_payload("12345678", ["27510", "99999"]), choose=choose)

        self.assertIn("99999", seen["texts"])
        self.assertEqual(self.page.employer_nace.currentText(), "99999")
        self.assertEqual(self.page._stored_employer_nace(), "99999")
        self.assertEqual(self.page.employer_nace.count(), self.catalog_count)

        self._save()
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.nace, "99999")

    def test_h_catalog_remains_complete_after_ares_workflow(self) -> None:
        def choose(dialog: EmployerNaceChoiceDialog):
            dialog.activities.setCurrentRow(dialog.activities.count() - 1)
            return dialog.selected_code()

        self._load(_payload("28196678", _CARGO_CODES), choose=choose)

        self.assertEqual(self.page.employer_nace.count(), self.catalog_count)
        self.assertGreater(self.page.employer_nace.findData("49.20"), -1)
        self.assertGreater(self.page.employer_nace.findData("62.10"), -1)
        self.assertGreater(self.page.employer_nace.findData("01.11"), -1)


if __name__ == "__main__":
    unittest.main()
