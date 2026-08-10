"""AGENDA-ANNUAL-PLAN-UX-1: zkrácení výběru roku Ročního plánu."""

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

    from moduly.rocni_plan.constants import (
        COL_TITLE,
        MAX_YEAR,
        MIN_YEAR,
        YEAR_COMBO_FUTURE_YEARS,
        YEAR_COMBO_MAX_VISIBLE,
        YEAR_COMBO_PAST_YEARS,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab


def _title_texts(tab: YearlyPlanTab) -> list[str]:
    return [
        tab.table.item(row, COL_TITLE).text()
        for row in range(tab.table.rowCount())
        if tab.table.item(row, COL_TITLE) is not None
    ]


class AgendaAnnualPlanUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_service_range_is_minus_5_plus_10(self) -> None:
        today = date(2026, 8, 10)
        with patch.object(
            yearly_plan_service,
            "list_used_years",
            return_value=[],
        ):
            years = yearly_plan_service.years_for_year_combo(today=today)
        self.assertEqual(years, list(range(2021, 2037)))
        self.assertIn(2026, years)
        self.assertNotIn(2018, years)
        self.assertNotIn(2050, years)
        self.assertLess(len(years), MAX_YEAR - MIN_YEAR)

    def test_used_year_outside_range_is_added_without_gap_fill(self) -> None:
        today = date(2026, 8, 10)
        with patch.object(
            yearly_plan_service,
            "list_used_years",
            return_value=[2018],
        ):
            years = yearly_plan_service.years_for_year_combo(today=today)
        self.assertEqual(years, [2018, *range(2021, 2037)])
        self.assertNotIn(2019, years)
        self.assertNotIn(2020, years)

    def test_tab_combo_defaults_and_limits(self) -> None:
        today = date.today()
        tab = YearlyPlanTab()
        years = tab._combo_years()

        self.assertEqual(tab.current_year(), today.year)
        self.assertIn(today.year, years)
        self.assertIn(today.year - YEAR_COMBO_PAST_YEARS, years)
        self.assertIn(today.year + YEAR_COMBO_FUTURE_YEARS, years)
        self.assertEqual(tab.year_combo.maxVisibleItems(), YEAR_COMBO_MAX_VISIBLE)
        self.assertLess(len(years), 40)
        self.assertNotEqual(len(years), MAX_YEAR - MIN_YEAR + 1)

    def test_tab_includes_historical_year_and_loads_plan(self) -> None:
        yearly_plan_service.create(year=2015, month=6, title="Položka 2015 UX1")
        tab = YearlyPlanTab()
        self.assertIn(2015, tab._combo_years())

        tab.set_year_month(2015, 6)
        self.assertEqual(tab.current_year(), 2015)
        self.assertIn("Položka 2015 UX1", _title_texts(tab))

    def test_changing_year_reloads_plan(self) -> None:
        yearly_plan_service.create(year=2027, month=1, title="Jen 2027 UX1")
        yearly_plan_service.create(year=2028, month=1, title="Jen 2028 UX1")
        tab = YearlyPlanTab()

        tab.set_year_month(2027, 1)
        texts_2027 = _title_texts(tab)
        self.assertIn("Jen 2027 UX1", texts_2027)
        self.assertNotIn("Jen 2028 UX1", texts_2027)

        tab.set_year_month(2028, 1)
        texts_2028 = _title_texts(tab)
        self.assertIn("Jen 2028 UX1", texts_2028)
        self.assertNotIn("Jen 2027 UX1", texts_2028)


if __name__ == "__main__":
    unittest.main()
