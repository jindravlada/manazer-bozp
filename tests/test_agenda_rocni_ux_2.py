"""AGENDA-ROCNI-UX-2: celoroční pohled Ročního plánu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QComboBox

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

    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.rocni_plan.constants import (
        COL_SOURCE,
        COL_TITLE,
        MONTH_NAMES,
        SOURCE_LABEL_PERIODIC,
        TAB_YEARLY_PLAN,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_item_dialog import YearlyPlanItemDialog
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab
    from moduly.rocni_plan.ui.yearly_plan_table import (
        _MONTH_HEADER_BG,
        format_month_header_parts,
        format_month_header_text,
    )
    from moduly.periodicke_cinnosti.constants import NEXT_FROM_PLANNED, UNIT_YEARS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )


class AgendaRocniUx2TestCase(unittest.TestCase):
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

    def test_all_twelve_months_visible(self) -> None:
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 1)
        # Pouze výběr roku nahoře (jeden QComboBox).
        combos = tab.findChildren(QComboBox)
        self.assertEqual(len(combos), 1)
        for month in range(1, 13):
            row = tab.table.month_header_row(month)
            self.assertIsNotNone(row, msg=f"Chybí měsíc {month}")
            self.assertFalse(tab.table.isRowHidden(row))
            text = tab.table.header_text_for_month(month)
            self.assertTrue(text.startswith(MONTH_NAMES[month - 1].capitalize()))
        tab.close()

    def test_items_under_correct_month(self) -> None:
        a = yearly_plan_service.create(year=2031, month=3, title="Březnová položka")
        b = yearly_plan_service.create(year=2031, month=8, title="Srpnová položka")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 3)

        march = tab.table.month_header_row(3)
        april = tab.table.month_header_row(4)
        august = tab.table.month_header_row(8)
        self.assertIsNotNone(march)
        self.assertIsNotNone(april)
        self.assertIsNotNone(august)

        titles_march = []
        for row in range(march + 1, april):
            titles_march.append(tab.table.item(row, COL_TITLE).text())
        self.assertIn("Březnová položka", titles_march)
        self.assertNotIn("Srpnová položka", titles_march)

        found_aug = False
        for row in range(august + 1, tab.table.rowCount()):
            next_header = tab.table.month_header_row(9)
            if next_header is not None and row >= next_header:
                break
            if tab.table.item(row, COL_TITLE).text() == "Srpnová položka":
                found_aug = True
        self.assertTrue(found_aug)
        self.assertEqual(a.month, 3)
        self.assertEqual(b.month, 8)
        tab.close()

    def test_empty_month_has_only_header(self) -> None:
        yearly_plan_service.create(year=2031, month=1, title="Jen leden")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 2)
        feb = tab.table.month_header_row(2)
        mar = tab.table.month_header_row(3)
        self.assertEqual(mar, feb + 1)
        text = tab.table.header_text_for_month(2)
        self.assertIn("Celkem: 0", text)
        self.assertNotIn("Žádné položky", text)
        tab.close()

    def test_month_header_style_and_not_selectable(self) -> None:
        from PySide6.QtCore import Qt

        tab = YearlyPlanTab()
        tab.set_year_month(2031, 5)
        row = tab.table.month_header_row(5)
        item = tab.table.item(row, COL_SOURCE)
        self.assertEqual(item.background().color().name().lower(), "#e3f2fd")
        self.assertEqual(_MONTH_HEADER_BG.name().lower(), "#e3f2fd")
        self.assertEqual(item.flags(), Qt.ItemFlag.NoItemFlags)
        tab.table.selectRow(row)
        # NoItemFlags – řádek měsíce nejde vybrat jako položku.
        self.assertIsNone(tab.table.selected_item_id())
        tab._refresh_action_buttons()
        self.assertFalse(tab.edit_btn.isEnabled())
        tab.close()

    def test_zebra_restarts_each_month(self) -> None:
        yearly_plan_service.create(year=2031, month=4, title="A1")
        yearly_plan_service.create(year=2031, month=4, title="A2")
        yearly_plan_service.create(year=2031, month=5, title="B1")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 4)
        palette = tab.table.palette()
        base = palette.color(QPalette.ColorRole.Base)
        alt = palette.color(QPalette.ColorRole.AlternateBase)

        april = tab.table.month_header_row(4)
        may = tab.table.month_header_row(5)
        first = tab.table.item(april + 1, COL_TITLE).background().color()
        second = tab.table.item(april + 2, COL_TITLE).background().color()
        may_first = tab.table.item(may + 1, COL_TITLE).background().color()
        self.assertEqual(first, base)
        self.assertEqual(second, alt)
        self.assertEqual(may_first, base)
        self.assertFalse(tab.table.alternatingRowColors())
        tab.close()

    def test_select_item_enables_actions(self) -> None:
        from PySide6.QtCore import Qt

        item = yearly_plan_service.create(year=2031, month=7, title="Akce")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 7)
        for row in range(tab.table.rowCount()):
            id_item = tab.table.item(row, 0)
            if id_item and id_item.data(Qt.ItemDataRole.UserRole) == item.id:
                tab.table.selectRow(row)
                break
        tab._refresh_action_buttons()
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.move_btn.isEnabled())
        tab.close()

    def test_new_item_prefills_year_allows_month(self) -> None:
        tab = YearlyPlanTab()
        tab.set_year_month(2032, 3)
        dialog = YearlyPlanItemDialog(
            tab,
            default_year=tab.current_year(),
            default_month=1,
        )
        self.assertEqual(dialog.year_combo.currentData(), 2032)
        self.assertGreaterEqual(dialog.month_combo.count(), 12)
        dialog.close()
        tab.close()

    def test_mark_month_processed_on_header(self) -> None:
        yearly_plan_service.mark_month_processed(
            2031,
            6,
            processed_at=datetime(2031, 6, 10, 8, 0, 0),
        )
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 6)
        text = tab.table.header_text_for_month(6)
        self.assertIn("Zpracováno:", text)
        self.assertIn("10. 6. 2031", text)
        tab.close()

    def test_open_from_dashboard_scrolls_to_month(self) -> None:
        page = AgendaPage()
        page.open_yearly_plan(2031, 11)
        tab = page.yearly_plan_tab
        self.assertEqual(page.tabs.tabText(page.tabs.currentIndex()), TAB_YEARLY_PLAN)
        self.assertEqual(tab.current_year(), 2031)
        self.assertEqual(tab.current_month(), 11)
        self.assertIsNotNone(tab.table.month_header_row(11))
        self.assertEqual(tab._focus_month, 11)
        page.close()

    def test_year_change_reloads_plan(self) -> None:
        yearly_plan_service.create(year=2031, month=2, title="2031 položka")
        yearly_plan_service.create(year=2033, month=2, title="2033 položka")
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 2)
        texts_2031 = [
            tab.table.item(row, COL_TITLE).text()
            for row in range(tab.table.rowCount())
            if tab.table.item(row, COL_TITLE) and tab.table.item(row, COL_TITLE).text()
        ]
        self.assertIn("2031 položka", texts_2031)
        self.assertNotIn("2033 položka", texts_2031)

        tab.set_year_month(2033, 2)
        texts_2033 = [
            tab.table.item(row, COL_TITLE).text()
            for row in range(tab.table.rowCount())
            if tab.table.item(row, COL_TITLE) and tab.table.item(row, COL_TITLE).text()
        ]
        self.assertIn("2033 položka", texts_2033)
        self.assertNotIn("2031 položka", texts_2033)
        tab.close()

    def test_format_month_header_text(self) -> None:
        text = format_month_header_text(
            8,
            {"total": 2, "done": 1, "in_progress": 0, "rest": 1, "cancelled": 0},
            processed_at=datetime(2031, 8, 5, 12, 0, 0),
        )
        self.assertTrue(text.startswith("Srpen"))
        self.assertIn("Celkem: 2", text)
        self.assertIn("Zpracováno: 5. 8. 2031", text)

    def test_month_header_bold_name_separate_from_summary(self) -> None:
        from moduly.rocni_plan.ui.yearly_plan_table import (
            _ROLE_HEADER_NAME,
            _ROLE_HEADER_SUMMARY,
        )

        name, summary = format_month_header_parts(
            3,
            {"total": 1, "done": 0, "in_progress": 1, "rest": 0, "cancelled": 0},
        )
        self.assertEqual(name, "Březen")
        self.assertTrue(summary.startswith("Celkem:"))
        self.assertNotIn("Březen", summary)

        tab = YearlyPlanTab()
        tab.set_year_month(2031, 3)
        row = tab.table.month_header_row(3)
        item = tab.table.item(row, COL_SOURCE)
        self.assertEqual(item.data(_ROLE_HEADER_NAME), "Březen")
        self.assertIn("Celkem:", item.data(_ROLE_HEADER_SUMMARY))
        self.assertNotEqual(
            item.data(_ROLE_HEADER_NAME),
            item.data(_ROLE_HEADER_SUMMARY),
        )
        tab.close()

    def test_periodic_still_listed(self) -> None:
        periodic_activity_service.create_activity(
            title="Periodika v roce",
            next_due_date=date(2031, 9, 10),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        tab = YearlyPlanTab()
        tab.set_year_month(2031, 9)
        titles = [
            tab.table.item(row, COL_TITLE).text()
            for row in range(tab.table.rowCount())
            if tab.table.item(row, COL_TITLE)
        ]
        self.assertIn("Periodika v roce", titles)
        sources = [
            tab.table.item(row, COL_SOURCE).text()
            for row in range(tab.table.rowCount())
            if tab.table.item(row, COL_SOURCE)
            and tab.table.item(row, COL_SOURCE).text() == SOURCE_LABEL_PERIODIC
        ]
        self.assertTrue(sources)
        tab.close()


if __name__ == "__main__":
    unittest.main()
