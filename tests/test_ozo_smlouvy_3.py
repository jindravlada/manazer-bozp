"""OZO-SMLOUVY-3: upozornění na konec platnosti smluv OZO."""

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

    from core.dashboard.attention_item import (
        ITEM_TYPE_OZO_CONTRACT,
        TYPE_LABELS,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_today import (
        TodayWidget,
        overdue_ozo_contract_items,
    )
    from core.windows.main_window import MainWindow
    from moduly.smlouvy_ozo.constants import UNIT_DAYS, UNIT_MONTHS
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoSmlouvy3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for contract in list(ozo_contract_service.get_all()):
            if contract.active:
                ozo_contract_service.deactivate(contract.id)

    def _create(self, **overrides):
        data = {
            "employer_name": "Firma OZO a.s.",
            "contract_number": "S-100",
            "valid_from": date(2030, 1, 1),
            "valid_to": date(2030, 6, 30),
            "indefinite": False,
            "notify_before_value": 30,
            "notify_before_unit": UNIT_DAYS,
            "active": True,
        }
        data.update(overrides)
        return ozo_contract_service.create(**data)

    def _ozo_items(self, today: date):
        return [
            item
            for item in get_attention_items(today=today)
            if item.item_type == ITEM_TYPE_OZO_CONTRACT
        ]

    def test_type_label(self) -> None:
        self.assertEqual(TYPE_LABELS[ITEM_TYPE_OZO_CONTRACT], "Smlouva OZO")

    def test_upcoming_from_notify_date(self) -> None:
        contract = self._create()
        # 30 dní před 30. 6. → od 31. 5.
        before = self._ozo_items(date(2030, 5, 30))
        self.assertFalse(any(item.source_id == contract.id for item in before))

        on_notify = self._ozo_items(date(2030, 5, 31))
        match = [item for item in on_notify if item.source_id == contract.id]
        self.assertEqual(len(match), 1)
        item = match[0]
        self.assertEqual(item.title, "Firma OZO a.s.")
        self.assertEqual(item.date, date(2030, 6, 30))
        self.assertEqual(item.type_label, "Smlouva OZO")
        self.assertIn("S-100", item.subtitle)
        self.assertEqual(item.status, "")

    def test_indefinite_never_in_attention(self) -> None:
        contract = self._create(
            indefinite=True,
            valid_to=None,
            employer_name="Neurčitá OZO",
        )
        items = self._ozo_items(date(2040, 1, 1))
        self.assertFalse(any(item.source_id == contract.id for item in items))

    def test_inactive_never_in_attention(self) -> None:
        contract = self._create(employer_name="Neaktivní OZO")
        ozo_contract_service.deactivate(contract.id)
        items = self._ozo_items(date(2030, 6, 15))
        self.assertFalse(any(item.source_id == contract.id for item in items))

    def test_expired_in_co_hori_and_upcoming(self) -> None:
        contract = self._create(
            employer_name="Po platnosti OZO",
            contract_number="S-EXP",
            valid_to=date(2030, 6, 30),
        )
        today = date(2030, 7, 1)
        items = self._ozo_items(today)
        match = [item for item in items if item.source_id == contract.id]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].status, "Po platnosti")
        self.assertIn("Po platnosti", match[0].subtitle)

        overdue = overdue_ozo_contract_items(today)
        self.assertTrue(any(item.source_id == contract.id for item in overdue))

        widget = TodayWidget()
        widget.refresh(today=today)
        text = widget.content.text()
        self.assertIn("Po platnosti OZO", text)
        self.assertIn("30.06.2030", text)
        self.assertIn("🔴", text)
        widget.close()

    def test_ending_not_in_co_hori(self) -> None:
        contract = self._create(employer_name="Jen končí OZO")
        today = date(2030, 6, 15)  # v předstihu, ještě ne po platnosti
        self.assertTrue(any(item.source_id == contract.id for item in self._ozo_items(today)))
        overdue = overdue_ozo_contract_items(today)
        self.assertFalse(any(item.source_id == contract.id for item in overdue))

        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertNotIn("Jen končí OZO", widget.content.text())
        widget.close()

    def test_extend_valid_to_updates_attention(self) -> None:
        contract = self._create(
            employer_name="Prodloužená OZO",
            valid_to=date(2030, 6, 30),
            notify_before_value=30,
            notify_before_unit=UNIT_DAYS,
        )
        today = date(2030, 6, 15)
        self.assertTrue(any(item.source_id == contract.id for item in self._ozo_items(today)))

        ozo_contract_service.update(
            contract.id,
            employer_name="Prodloužená OZO",
            valid_from=date(2030, 1, 1),
            valid_to=date(2031, 6, 30),
            indefinite=False,
            notify_before_value=30,
            notify_before_unit=UNIT_DAYS,
        )
        self.assertFalse(any(item.source_id == contract.id for item in self._ozo_items(today)))

    def test_individual_months_lead(self) -> None:
        contract = self._create(
            employer_name="Měsíce OZO",
            notify_before_value=2,
            notify_before_unit=UNIT_MONTHS,
            valid_to=date(2030, 6, 30),
        )
        self.assertFalse(
            any(
                item.source_id == contract.id
                for item in self._ozo_items(date(2030, 4, 29))
            )
        )
        self.assertTrue(
            any(
                item.source_id == contract.id
                for item in self._ozo_items(date(2030, 4, 30))
            )
        )

    def test_open_contract_from_attention(self) -> None:
        contract = self._create(employer_name="Otevřít z dashboardu")
        opened: list[int] = []

        window = MainWindow()
        page = window._page_widgets.get("smlouvy_ozo")
        if page is None:
            window._show("smlouvy_ozo")
            page = window._page_widgets.get("smlouvy_ozo")
        self.assertIsNotNone(page)

        original = page.open_contract

        def _track(contract_id: int) -> None:
            opened.append(contract_id)

        with patch.object(page, "open_contract", side_effect=_track):
            item = type(
                "Item",
                (),
                {
                    "item_type": ITEM_TYPE_OZO_CONTRACT,
                    "source_id": contract.id,
                    "open_metadata": {},
                },
            )()
            window._open_attention_item(item)

        self.assertEqual(opened, [contract.id])
        self.assertIn("smlouvy_ozo", window._page_widgets)
        self.assertTrue(callable(original))
        window.close()

    def test_dashboard_refresh_callback_on_edit(self) -> None:
        contract = self._create(employer_name="Refresh OZO")
        refreshed = []

        page = SmlouvyOzoPage()
        page.set_dashboard_refresh_callback(lambda: refreshed.append(True))
        with patch(
            "moduly.smlouvy_ozo.ui.smlouvy_ozo_page.exec_maximized",
            return_value=True,
        ), patch(
            "moduly.smlouvy_ozo.ui.smlouvy_ozo_page.OzoContractDialog",
        ) as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.contract = contract
            page.open_contract(contract.id)

        self.assertTrue(refreshed)
        page.close()


if __name__ == "__main__":
    unittest.main()
