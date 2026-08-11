"""OZO-SMLOUVY-2: evidence smluv OZO."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.modules.module_manager import ModuleManager
    from core.services.attachment_service import attachment_service
    from core.windows.main_window import MainWindow
    from moduly.smlouvy_ozo.constants import (
        ACTION_EDIT,
        ACTION_NEW,
        COL_EMPLOYER,
        COL_STATUS,
        COLUMN_HEADERS,
        ENTITY_OZO_CONTRACT,
        MODULE_KEY,
        MODULE_NAME,
        STATUS_ACTIVE,
        STATUS_ENDING,
        STATUS_EXPIRED,
        STATUS_INACTIVE,
        UNIT_DAYS,
        UNIT_MONTHS,
        UNIT_WEEKS,
        status_label,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import (
        OzoContractValidationError,
        ozo_contract_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_validity import contract_status
    from moduly.smlouvy_ozo.ui.ozo_contract_dialog import OzoContractDialog
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoSmlouvy2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._ico_seq = 0
        for contract in list(ozo_contract_service.get_all()):
            ozo_contract_service.deactivate(contract.id)
            # Soft cleanup: leave inactive; create unique names per test.

    def _next_ico(self) -> str:
        self._ico_seq += 1
        return f"{self._ico_seq:08d}"

    def _create(self, **overrides):
        data = {
            "employer_name": "Test Objednatel a.s.",
            "ico": self._next_ico(),
            "address": "Praha 1",
            "valid_from": date(2030, 1, 1),
            "valid_to": date(2030, 12, 31),
            "indefinite": False,
            "notify_before_value": 30,
            "notify_before_unit": UNIT_DAYS,
            "active": True,
        }
        data.update(overrides)
        return ozo_contract_service.create(**data)

    def test_module_registered_above_sprava_dat(self) -> None:
        keys = [m.key for m in ModuleManager().get_modules()]
        self.assertIn(MODULE_KEY, keys)
        self.assertLess(keys.index(MODULE_KEY), keys.index("sprava_dat"))

        window = MainWindow()
        sidebar_keys = list(window._sidebar_buttons.keys())
        self.assertIn(MODULE_KEY, sidebar_keys)
        self.assertEqual(
            window._sidebar_buttons[MODULE_KEY].text(),
            MODULE_NAME,
        )
        self.assertLess(
            sidebar_keys.index(MODULE_KEY),
            sidebar_keys.index("sprava_dat"),
        )
        self.assertLess(
            sidebar_keys.index("sprava_dat"),
            sidebar_keys.index("nastaveni"),
        )
        window.close()

    def test_column_headers(self) -> None:
        self.assertEqual(
            list(COLUMN_HEADERS),
            [
                "ID",
                "Zaměstnavatel",
                "IČO",
                "Číslo smlouvy",
                "Platnost od",
                "Platnost do",
                "Stav",
            ],
        )

    def test_create_and_edit_contract(self) -> None:
        contract = self._create(contract_number="S-1")
        self.assertEqual(contract.employer_name, "Test Objednatel a.s.")
        updated = ozo_contract_service.update(
            contract.id,
            employer_name="Upravený s.r.o.",
            contract_number="S-2",
            valid_from=date(2030, 2, 1),
            valid_to=date(2031, 1, 31),
            indefinite=False,
        )
        self.assertEqual(updated.employer_name, "Upravený s.r.o.")
        self.assertEqual(updated.contract_number, "S-2")

    def test_required_fields(self) -> None:
        with self.assertRaises(OzoContractValidationError):
            ozo_contract_service.create(
                employer_name="",
                valid_from=date(2030, 1, 1),
                valid_to=date(2030, 12, 31),
            )
        with self.assertRaises(OzoContractValidationError):
            ozo_contract_service.create(
                employer_name="Firma",
                valid_from=None,
                valid_to=date(2030, 12, 31),
            )
        with self.assertRaises(OzoContractValidationError):
            ozo_contract_service.create(
                employer_name="Firma",
                valid_from=date(2030, 1, 1),
                indefinite=False,
                valid_to=None,
            )

    def test_indefinite_clears_valid_to(self) -> None:
        contract = self._create(
            indefinite=True,
            valid_to=date(2030, 12, 31),
        )
        self.assertTrue(contract.indefinite)
        self.assertIsNone(contract.valid_to)
        self.assertEqual(
            ozo_contract_service.status_for(contract, today=date(2035, 1, 1)),
            STATUS_ACTIVE,
        )

    def test_status_active_ending_expired(self) -> None:
        self.assertEqual(
            contract_status(
                active=True,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                notify_before_value=30,
                notify_before_unit=UNIT_DAYS,
                today=date(2030, 5, 1),
            ),
            STATUS_ACTIVE,
        )
        self.assertEqual(
            contract_status(
                active=True,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                notify_before_value=30,
                notify_before_unit=UNIT_DAYS,
                today=date(2030, 6, 1),
            ),
            STATUS_ENDING,
        )
        self.assertEqual(
            contract_status(
                active=True,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                notify_before_value=30,
                notify_before_unit=UNIT_DAYS,
                today=date(2030, 7, 1),
            ),
            STATUS_EXPIRED,
        )
        self.assertEqual(
            contract_status(
                active=False,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                today=date(2030, 5, 1),
            ),
            STATUS_INACTIVE,
        )

    def test_individual_notify_lead(self) -> None:
        # 2 měsíce předstih → 30. 4. už Končí při konci 30. 6.
        self.assertEqual(
            contract_status(
                active=True,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                notify_before_value=2,
                notify_before_unit=UNIT_MONTHS,
                today=date(2030, 4, 30),
            ),
            STATUS_ENDING,
        )
        self.assertEqual(
            contract_status(
                active=True,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                notify_before_value=2,
                notify_before_unit=UNIT_WEEKS,
                today=date(2030, 6, 16),
            ),
            STATUS_ENDING,
        )
        self.assertEqual(
            contract_status(
                active=True,
                indefinite=False,
                valid_to=date(2030, 6, 30),
                notify_before_value=2,
                notify_before_unit=UNIT_WEEKS,
                today=date(2030, 6, 10),
            ),
            STATUS_ACTIVE,
        )

    def test_activate_deactivate(self) -> None:
        contract = self._create()
        deactivated = ozo_contract_service.deactivate(contract.id)
        self.assertFalse(deactivated.active)
        self.assertEqual(
            ozo_contract_service.status_for(deactivated),
            STATUS_INACTIVE,
        )
        activated = ozo_contract_service.activate(contract.id)
        self.assertTrue(activated.active)

    def _select_all_years(self, page: SmlouvyOzoPage) -> None:
        page.year_filter.setValue(page.year_filter.minimum())
        self.assertIsNone(page.selected_year())

    def test_inactive_filter_default(self) -> None:
        active = self._create(employer_name="Aktivní OZO")
        inactive = self._create(employer_name="Neaktivní OZO")
        ozo_contract_service.deactivate(inactive.id)

        page = SmlouvyOzoPage()
        self._select_all_years(page)
        names = [
            page.table.item(row, COL_EMPLOYER).text()
            for row in range(page.table.rowCount())
        ]
        self.assertIn("Aktivní OZO", names)
        self.assertNotIn("Neaktivní OZO", names)

        page.show_inactive.setChecked(True)
        page.refresh()
        names = [
            page.table.item(row, COL_EMPLOYER).text()
            for row in range(page.table.rowCount())
        ]
        self.assertIn("Aktivní OZO", names)
        self.assertIn("Neaktivní OZO", names)
        page.close()
        # keep ids referenced
        self.assertIsNotNone(active.id)

    def test_action_buttons_by_selection(self) -> None:
        self._create(employer_name="Tlačítka OZO")
        page = SmlouvyOzoPage()
        self._select_all_years(page)
        self.assertEqual(page.new_btn.text(), ACTION_NEW)
        self.assertEqual(page.edit_btn.text(), ACTION_EDIT)
        self.assertFalse(hasattr(page, "activate_btn"))
        self.assertFalse(hasattr(page, "deactivate_btn"))
        self.assertFalse(page.edit_btn.isEnabled())

        for row in range(page.table.rowCount()):
            if page.table.item(row, COL_EMPLOYER).text() == "Tlačítka OZO":
                page.table.selectRow(row)
                break
        page._refresh_action_buttons()
        self.assertTrue(page.edit_btn.isEnabled())
        page.close()

    def test_list_status_column(self) -> None:
        self._create(
            employer_name="Končí brzy",
            valid_from=date(2030, 1, 1),
            valid_to=date(2030, 6, 30),
            notify_before_value=60,
            notify_before_unit=UNIT_DAYS,
        )
        page = SmlouvyOzoPage()
        # vynucení dnes přes load_contracts
        contracts = ozo_contract_service.get_all(active_only=True)
        page.table.load_contracts(contracts, today=date(2030, 5, 15))
        found = False
        for row in range(page.table.rowCount()):
            if page.table.item(row, COL_EMPLOYER).text() == "Končí brzy":
                self.assertEqual(
                    page.table.item(row, COL_STATUS).text(),
                    status_label(STATUS_ENDING),
                )
                found = True
        self.assertTrue(found)
        page.close()

    def test_ares_loads_name_and_address(self) -> None:
        dialog = OzoContractDialog()
        dialog.ico.setText("00000000")
        with patch(
            "moduly.smlouvy_ozo.ui.ozo_contract_dialog.ares_service.find_by_ico",
            return_value={
                "ico": "00000000",
                "name": "ARES Firma s.r.o.",
                "address": "Ulice 1, Praha",
            },
        ):
            dialog.load_from_ares()
        self.assertEqual(dialog.employer_name.text(), "ARES Firma s.r.o.")
        self.assertEqual(dialog.address.text(), "Ulice 1, Praha")
        self.assertEqual(dialog.ico.text(), "00000000")
        dialog.close()

    def test_dialog_indefinite_disables_notify(self) -> None:
        dialog = OzoContractDialog()
        dialog.indefinite_checkbox.setChecked(True)
        self.assertFalse(dialog.valid_to.isEnabled())
        self.assertFalse(dialog.notify_widget.isEnabled())
        dialog.indefinite_checkbox.setChecked(False)
        self.assertTrue(dialog.valid_to.isEnabled())
        self.assertTrue(dialog.notify_widget.isEnabled())
        dialog.close()

    def test_attachments_after_save(self) -> None:
        dialog = OzoContractDialog()
        dialog.employer_name.setText("S přílohou")
        dialog.valid_from.set_date_value(date(2030, 1, 1))
        dialog.valid_to.set_date_value(date(2030, 12, 31))
        self.assertIsNone(dialog.attachments.entity_id)
        self.assertFalse(dialog.attachments.btn_add.isEnabled())
        self.assertTrue(dialog._save())
        self.assertIsNotNone(dialog.contract)
        self.assertEqual(dialog.attachments.entity_type, ENTITY_OZO_CONTRACT)
        self.assertEqual(dialog.attachments.entity_id, dialog.contract.id)
        self.assertTrue(dialog.attachments.btn_add.isEnabled())

        tmp = Path(tempfile.mkdtemp()) / "smlouva.pdf"
        tmp.write_bytes(b"%PDF-test")
        attachment_service.add_file(ENTITY_OZO_CONTRACT, dialog.contract.id, str(tmp))
        items = attachment_service.get_for_entity(
            ENTITY_OZO_CONTRACT, dialog.contract.id
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].filename, "smlouva.pdf")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
