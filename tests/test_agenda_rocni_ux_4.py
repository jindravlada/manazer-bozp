"""AGENDA-ROCNI-UX-4: zpracování vybraného měsíce a pořadí sloupců."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

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
        ACTION_MARK_MONTH_PROCESSED,
        COL_LINK,
        COL_NOTE,
        COL_SOURCE,
        COL_STATUS,
        COL_TITLE,
        COLUMN_HEADERS,
        SOURCE_LABEL_PERIODIC,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab
    from moduly.periodicke_cinnosti.constants import NEXT_FROM_PLANNED, UNIT_YEARS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )


class AgendaRocniUx4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for year in range(2025, 2035):
            for month in range(1, 13):
                yearly_plan_service.month_status_repository.delete_for_month(
                    year, month
                )
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.status != "cancelled":
                    yearly_plan_service.cancel(item.id)
        for activity in list(periodic_activity_service.get_all()):
            periodic_activity_service.update_activity(
                activity.id,
                title=f"OLD-{activity.id}-{activity.title}",
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
            )

    def _select_month_header(self, tab: YearlyPlanTab, month: int) -> None:
        row = tab.table.month_header_row(month)
        self.assertIsNotNone(row)
        tab.table.selectRow(row)
        tab._refresh_action_buttons()

    def _select_item_row(self, tab: YearlyPlanTab, item_id: int) -> None:
        for row in range(tab.table.rowCount()):
            id_item = tab.table.item(row, 0)
            if id_item and id_item.data(Qt.ItemDataRole.UserRole) == item_id:
                tab.table.selectRow(row)
                tab._refresh_action_buttons()
                return
        self.fail(f"Položka {item_id} nenalezena v tabulce")

    def test_column_order_title_first_source_last(self) -> None:
        self.assertEqual(
            list(COLUMN_HEADERS),
            ["ID", "Název", "Stav", "Vazba", "Poznámka", "Zdroj"],
        )
        self.assertEqual(COL_TITLE, 1)
        self.assertEqual(COL_STATUS, 2)
        self.assertEqual(COL_LINK, 3)
        self.assertEqual(COL_NOTE, 4)
        self.assertEqual(COL_SOURCE, 5)

        item = yearly_plan_service.create(year=2031, month=4, title="Pořadí")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 4)
        self.assertEqual(
            [
                tab.table.horizontalHeaderItem(i).text()
                for i in range(1, tab.table.columnCount())
            ],
            ["Název", "Stav", "Vazba", "Poznámka", "Zdroj"],
        )
        self._select_item_row(tab, item.id)
        self.assertEqual(tab.table.item(
            tab.table.selectionModel().selectedRows()[0].row(),
            COL_TITLE,
        ).text(), "Pořadí")
        self.assertEqual(tab.table.item(
            tab.table.selectionModel().selectedRows()[0].row(),
            COL_SOURCE,
        ).text(), "Roční plán")
        self.assertTrue(tab.edit_btn.isEnabled())
        tab.close()

    def test_mark_month_default_disabled(self) -> None:
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 3)
        self.assertEqual(tab.mark_month_btn.text(), ACTION_MARK_MONTH_PROCESSED)
        self.assertFalse(tab.mark_month_btn.isEnabled())
        self.assertTrue(tab.new_btn.isEnabled())
        tab.close()

    def test_unprocessed_month_header_enables_mark(self) -> None:
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 3)
        self._select_month_header(tab, 3)
        self.assertTrue(tab.table.selected_is_month_header())
        self.assertEqual(tab.table.selected_header_month(), 3)
        self.assertTrue(tab.mark_month_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.create_task_btn.isEnabled())
        self.assertFalse(tab.create_meeting_btn.isEnabled())
        self.assertFalse(tab.move_btn.isEnabled())
        self.assertFalse(tab.cancel_btn.isEnabled())
        self.assertTrue(tab.new_btn.isEnabled())
        tab.close()

    def test_processed_month_header_keeps_mark_disabled(self) -> None:
        yearly_plan_service.mark_month_processed(
            2031,
            5,
            processed_at=datetime(2031, 5, 12, 9, 0, 0),
        )
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 5)
        text = tab.table.header_text_for_month(5)
        self.assertIn("Zpracováno:", text)
        self.assertIn("12. 5. 2031", text)
        self._select_month_header(tab, 5)
        self.assertFalse(tab.mark_month_btn.isEnabled())
        tab.close()

    def test_item_selection_disables_mark_month(self) -> None:
        item = yearly_plan_service.create(year=2031, month=7, title="Ruční")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 7)
        self._select_month_header(tab, 7)
        self.assertTrue(tab.mark_month_btn.isEnabled())
        self._select_item_row(tab, item.id)
        self.assertFalse(tab.mark_month_btn.isEnabled())
        self.assertTrue(tab.edit_btn.isEnabled())
        tab.close()

    def test_periodic_selection_disables_mark_month(self) -> None:
        from datetime import date

        periodic_activity_service.create_activity(
            title="Periodika UX4",
            next_due_date=date(2031, 8, 15),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 8)
        found = False
        for row in range(tab.table.rowCount()):
            source = tab.table.item(row, COL_SOURCE)
            if source and source.text() == SOURCE_LABEL_PERIODIC:
                tab.table.selectRow(row)
                tab._refresh_action_buttons()
                found = True
                break
        self.assertTrue(found)
        self.assertFalse(tab.mark_month_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        tab.close()

    def test_no_month_pick_dialog(self) -> None:
        import importlib.util

        path = Path("moduly/rocni_plan/ui/yearly_plan_month_pick_dialog.py")
        self.assertFalse(path.exists())
        self.assertIsNone(
            importlib.util.find_spec(
                "moduly.rocni_plan.ui.yearly_plan_month_pick_dialog"
            )
        )
        tab = YearlyPlanTab()
        self.assertIsNone(tab._month_for_mark_action())
        tab.close()

    def test_mark_selected_month_processed(self) -> None:
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 9)
        self._select_month_header(tab, 9)
        self.assertTrue(tab.mark_month_btn.isEnabled())
        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab.mark_month_processed()
        self.assertTrue(yearly_plan_service.is_month_processed(2031, 9))
        text = tab.table.header_text_for_month(9)
        self.assertIn("Zpracováno:", text)
        self.assertFalse(tab.mark_month_btn.isEnabled())
        tab.close()

    def test_month_header_span_covers_visible_columns(self) -> None:
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 1)
        row = tab.table.month_header_row(1)
        # Span začíná u Název a pokrývá 5 viditelných sloupců.
        self.assertEqual(tab.table.columnSpan(row, COL_TITLE), 5)
        self.assertTrue(tab.table.item(row, COL_TITLE).text().startswith("Leden"))
        tab.close()


if __name__ == "__main__":
    unittest.main()
