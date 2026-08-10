"""AGENDA-ANNUAL-PLAN-UX-2: volný výběr roku Ročního plánu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QSpinBox

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
        YEAR_SPIN_MAX,
        YEAR_SPIN_MIN,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab


def _title_texts(tab: YearlyPlanTab) -> list[str]:
    return [
        tab.table.item(row, COL_TITLE).text()
        for row in range(tab.table.rowCount())
        if tab.table.item(row, COL_TITLE) is not None
    ]


class AgendaAnnualPlanUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_defaults_to_current_year_spinbox(self) -> None:
        tab = YearlyPlanTab()
        self.assertIsInstance(tab.year_spin, QSpinBox)
        self.assertEqual(tab.year_spin.minimum(), YEAR_SPIN_MIN)
        self.assertEqual(tab.year_spin.maximum(), YEAR_SPIN_MAX)
        self.assertEqual(tab.year_spin.singleStep(), 1)
        self.assertEqual(tab.current_year(), date.today().year)
        self.assertFalse(hasattr(tab, "year_combo"))

    def test_manual_historical_and_future_years(self) -> None:
        yearly_plan_service.create(year=2005, month=3, title="Položka 2005 UX2")
        yearly_plan_service.create(year=2045, month=8, title="Položka 2045 UX2")
        tab = YearlyPlanTab()

        tab.year_spin.setValue(2005)
        self.assertEqual(tab.current_year(), 2005)
        self.assertIn("Položka 2005 UX2", _title_texts(tab))
        self.assertNotIn("Položka 2045 UX2", _title_texts(tab))

        tab.year_spin.setValue(2045)
        self.assertEqual(tab.current_year(), 2045)
        self.assertIn("Položka 2045 UX2", _title_texts(tab))
        self.assertNotIn("Položka 2005 UX2", _title_texts(tab))

    def test_arrow_step_changes_year_by_one(self) -> None:
        tab = YearlyPlanTab()
        start = tab.current_year()
        tab.year_spin.stepBy(1)
        self.assertEqual(tab.current_year(), start + 1)
        tab.year_spin.stepBy(-1)
        self.assertEqual(tab.current_year(), start)

    def test_set_year_month_loads_plan(self) -> None:
        yearly_plan_service.create(year=2031, month=4, title="Abril UX2")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 4)
        self.assertEqual(tab.current_year(), 2031)
        self.assertEqual(tab.current_month(), 4)
        self.assertIn("Abril UX2", _title_texts(tab))


if __name__ == "__main__":
    unittest.main()
