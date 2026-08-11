"""OZO-SMLOUVY: výběr roku v přehledu přes QSpinBox (včetně „Vše“)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel, QSpinBox

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

    from moduly.smlouvy_ozo.constants import (
        COL_EMPLOYER,
        YEAR_FILTER_ALL,
        YEAR_SPIN_ALL_VALUE,
        YEAR_SPIN_MAX,
        YEAR_SPIN_MIN,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


def _employer_names(page: SmlouvyOzoPage) -> list[str]:
    return [
        page.table.item(row, COL_EMPLOYER).text()
        for row in range(page.table.rowCount())
        if page.table.item(row, COL_EMPLOYER) is not None
    ]


class OzoSmlouvyYearSpinTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract

        self._ico_seq = 0
        with get_session() as session:
            session.execute(delete(OzoContract))
            session.commit()

    def _next_ico(self) -> str:
        self._ico_seq += 1
        return f"{self._ico_seq:08d}"

    def _create(self, **overrides):
        data = {
            "employer_name": "Objednatel A",
            "ico": self._next_ico(),
            "valid_from": date(2030, 3, 1),
            "valid_to": date(2030, 12, 31),
            "indefinite": False,
            "active": True,
        }
        data.update(overrides)
        return ozo_contract_service.create(**data)

    def test_year_filter_is_spinbox_with_all_special_value(self) -> None:
        page = SmlouvyOzoPage()
        self.assertIsInstance(page.year_filter, QSpinBox)
        self.assertEqual(page.year_filter.minimum(), YEAR_SPIN_ALL_VALUE)
        self.assertEqual(page.year_filter.maximum(), YEAR_SPIN_MAX)
        self.assertEqual(page.year_filter.specialValueText(), YEAR_FILTER_ALL)
        self.assertEqual(page.year_filter.singleStep(), 1)
        self.assertEqual(page.selected_year(), date.today().year)
        labels = [
            label.text()
            for label in page.findChildren(QLabel)
            if label.text() == "Rok:"
        ]
        self.assertEqual(labels, ["Rok:"])
        # Rozsah skutečných roků je 1900–2100 (pod 1900 jen „Vše“).
        page.year_filter.setValue(YEAR_SPIN_MIN)
        self.assertEqual(page.selected_year(), YEAR_SPIN_MIN)
        page.year_filter.setValue(YEAR_SPIN_MAX)
        self.assertEqual(page.selected_year(), YEAR_SPIN_MAX)
        page.close()

    def test_year_filter_filters_by_selected_year(self) -> None:
        self._create(
            employer_name="Smlouva 2030",
            signed_on=date(2030, 6, 1),
            valid_from=date(2030, 6, 1),
            valid_to=date(2030, 12, 31),
        )
        self._create(
            employer_name="Smlouva 2031",
            signed_on=date(2031, 1, 5),
            valid_from=date(2031, 1, 5),
            valid_to=date(2031, 12, 31),
        )

        page = SmlouvyOzoPage()
        page.year_filter.setValue(2030)
        names = _employer_names(page)
        self.assertEqual(page.selected_year(), 2030)
        self.assertIn("Smlouva 2030", names)
        self.assertNotIn("Smlouva 2031", names)

        page.year_filter.setValue(2031)
        names = _employer_names(page)
        self.assertEqual(page.selected_year(), 2031)
        self.assertIn("Smlouva 2031", names)
        self.assertNotIn("Smlouva 2030", names)
        page.close()

    def test_year_filter_all_shows_contracts_without_year_limit(self) -> None:
        self._create(
            employer_name="Rok A",
            signed_on=date(2028, 3, 1),
            valid_from=date(2028, 3, 1),
            valid_to=date(2028, 12, 31),
        )
        self._create(
            employer_name="Rok B",
            signed_on=date(2032, 4, 1),
            valid_from=date(2032, 4, 1),
            valid_to=date(2032, 12, 31),
        )

        page = SmlouvyOzoPage()
        page.year_filter.setValue(YEAR_SPIN_ALL_VALUE)
        self.assertIsNone(page.selected_year())
        self.assertEqual(page.year_filter.cleanText(), YEAR_FILTER_ALL)
        names = _employer_names(page)
        self.assertIn("Rok A", names)
        self.assertIn("Rok B", names)
        page.close()


if __name__ == "__main__":
    unittest.main()
