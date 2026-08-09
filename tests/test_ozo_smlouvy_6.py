"""OZO-SMLOUVY-6: upozornění na končící smlouvy."""

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
        SOURCE_LABEL_OZO_CONTRACT,
        TYPE_LABELS,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_today import (
        TodayWidget,
        overdue_ozo_contract_items,
    )
    from core.windows.main_window import MainWindow
    from moduly.smlouvy_ozo.constants import UNIT_DAYS, UNIT_WEEKS
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoSmlouvy6TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract

        with get_session() as session:
            session.execute(delete(OzoContract))
            session.commit()

    def _create(self, **overrides):
        data = {
            "employer_name": "Objednatel OZO a.s.",
            "ico": "87654321",
            "contract_number": "S-600",
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

    def test_labels(self) -> None:
        self.assertEqual(TYPE_LABELS[ITEM_TYPE_OZO_CONTRACT], "Smlouva OZO")
        self.assertEqual(SOURCE_LABEL_OZO_CONTRACT, "Smlouvy OZO")

    def test_before_notify_date_hidden(self) -> None:
        contract = self._create()
        # 30 dní před 30. 6. → od 31. 5.; 30. 5. ještě ne
        items = self._ozo_items(date(2030, 5, 30))
        self.assertFalse(any(item.source_id == contract.id for item in items))

    def test_on_notify_date_shown(self) -> None:
        contract = self._create()
        items = self._ozo_items(date(2030, 5, 31))
        match = [item for item in items if item.source_id == contract.id]
        self.assertEqual(len(match), 1)
        item = match[0]
        self.assertEqual(item.type_label, "Smlouva OZO")
        self.assertEqual(item.date, date(2030, 6, 30))
        self.assertEqual(item.title, "Objednatel OZO a.s.")
        self.assertIn("Smlouvy OZO", item.subtitle)
        self.assertIn("S-600", item.subtitle)
        self.assertEqual(item.status, "")

    def test_between_notify_and_valid_to_shown(self) -> None:
        contract = self._create()
        items = self._ozo_items(date(2030, 6, 15))
        self.assertTrue(any(item.source_id == contract.id for item in items))
        overdue = overdue_ozo_contract_items(date(2030, 6, 15))
        self.assertFalse(any(item.source_id == contract.id for item in overdue))

    def test_after_valid_to_expired_and_burning(self) -> None:
        contract = self._create(employer_name="Po platnosti 6")
        today = date(2030, 7, 1)
        match = [item for item in self._ozo_items(today) if item.source_id == contract.id]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].status, "Po platnosti")
        self.assertIn("Po platnosti", match[0].subtitle)
        self.assertTrue(
            any(item.source_id == contract.id for item in overdue_ozo_contract_items(today))
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertIn("Po platnosti 6", widget.content.text())
        self.assertIn("🔴", widget.content.text())
        widget.close()

    def test_indefinite_never_shown(self) -> None:
        contract = self._create(
            employer_name="Neurčitá 6",
            indefinite=True,
            valid_to=None,
        )
        self.assertFalse(
            any(item.source_id == contract.id for item in self._ozo_items(date(2040, 1, 1)))
        )

    def test_archived_active_false_never_shown(self) -> None:
        contract = self._create(employer_name="Archiv 6")
        ozo_contract_service.deactivate(contract.id)
        self.assertFalse(
            any(item.source_id == contract.id for item in self._ozo_items(date(2030, 6, 15)))
        )

    def test_weeks_notify_unit(self) -> None:
        contract = self._create(
            employer_name="Týdny 6",
            notify_before_value=2,
            notify_before_unit=UNIT_WEEKS,
            valid_to=date(2030, 6, 30),
        )
        # 2 týdny před 30. 6. = od 16. 6.
        self.assertFalse(
            any(
                item.source_id == contract.id
                for item in self._ozo_items(date(2030, 6, 15))
            )
        )
        self.assertTrue(
            any(
                item.source_id == contract.id
                for item in self._ozo_items(date(2030, 6, 16))
            )
        )

    def test_valid_to_change_recalculates_attention(self) -> None:
        contract = self._create(
            employer_name="Změna termínu 6",
            valid_to=date(2030, 6, 30),
            notify_before_value=30,
            notify_before_unit=UNIT_DAYS,
        )
        today = date(2030, 6, 15)
        self.assertTrue(any(item.source_id == contract.id for item in self._ozo_items(today)))
        ozo_contract_service.update(
            contract.id,
            employer_name="Změna termínu 6",
            ico="87654321",
            valid_from=date(2030, 1, 1),
            valid_to=date(2031, 6, 30),
            indefinite=False,
            notify_before_value=30,
            notify_before_unit=UNIT_DAYS,
        )
        self.assertFalse(any(item.source_id == contract.id for item in self._ozo_items(today)))

    def test_dashboard_refresh_on_edit(self) -> None:
        contract = self._create(employer_name="Refresh 6")
        refreshed: list[bool] = []
        page = SmlouvyOzoPage()
        page.set_dashboard_refresh_callback(lambda: refreshed.append(True))
        with patch(
            "moduly.smlouvy_ozo.ui.smlouvy_ozo_page.exec_maximized",
            return_value=True,
        ), patch(
            "moduly.smlouvy_ozo.ui.smlouvy_ozo_page.OzoContractDialog",
        ) as dialog_cls:
            dialog_cls.return_value.contract = contract
            page.open_contract(contract.id)
        self.assertTrue(refreshed)
        page.close()

    def test_open_leads_to_contract(self) -> None:
        contract = self._create(employer_name="Otevřít 6")
        opened: list[int] = []
        window = MainWindow()
        page = window._page_widgets.get("smlouvy_ozo")
        if page is None:
            window._show("smlouvy_ozo")
            page = window._page_widgets.get("smlouvy_ozo")
        self.assertIsNotNone(page)

        with patch.object(page, "open_contract", side_effect=opened.append):
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
        window.close()


if __name__ == "__main__":
    unittest.main()
