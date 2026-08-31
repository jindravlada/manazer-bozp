"""STATE-SUPERVISION-OVERVIEW-2A: čtecí přehled v Agendě."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-overview-2a-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.theme.status_colors import (
        STATUS_DONE_BG,
        STATUS_IN_PROGRESS_BG,
        STATUS_NEUTRAL_BG,
        STATUS_WAITING_BG,
        STATUS_WARNING_BG,
    )
    from core.widgets.table_utils import table_cell_text_is_elided
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        COL_AUTHORITY,
        COL_ENDED,
        COL_RESULT,
        COL_STARTED,
        COL_STATUS,
        COL_WORKPLACE,
        COLUMN_HEADERS,
        EMPTY_STATE_FILTER,
        EMPTY_STATE_NONE,
        EMPTY_VALUE,
        FILTER_ALL,
        FILTER_MODE_ACTIVE,
        FILTER_MODE_CLOSED,
        LOAD_ERROR_TEXT,
        STATE_SUPERVISION_STATUS_HINTS,
        STATE_SUPERVISION_STATUS_LABELS,
        STATE_SUPERVISION_STATUS_ORDER,
        STATUS_ANNOUNCED,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_CUBE_HINT,
        STATUS_IN_PROGRESS,
        STATUS_MEASURES_IN_PROGRESS,
        STATUS_OBJECTIONS_PERIOD,
        STATUS_PREPARATION,
        STATUS_WAITING_AUTHORITY_CONFIRMATION,
        STATUS_WAITING_PROTOCOL,
        TAB_STATE_SUPERVISION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab
    from moduly.statni_dozor.ui.state_supervision_table import (
        STATUS_CUBE_COLORS,
        StatusCubeDelegate,
        format_supervision_date,
        status_cube_tooltip,
    )


def _count_supervisions() -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM state_supervisions").fetchone()[0])
    finally:
        conn.close()


class StateSupervisionOverview2aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(
            name=f"SD-Přehled-{self.marker}",
            address="Ulice 1",
            active=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def _create(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _open_page(self) -> AgendaPage:
        page = AgendaPage()
        page.tabs.setCurrentIndex(1)
        return page

    def test_01_four_tabs_in_order(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.state_supervision_tab, StateSupervisionTab)
        self.assertEqual(page.tabs.indexOf(page.state_supervision_tab), 1)
        self.assertEqual(page.tabs.indexOf(page.periodic_tab), 2)
        self.assertEqual(page.tabs.indexOf(page.yearly_plan_tab), 3)
        page.close()

    def test_02_default_filter_all_and_toolbar_actions(self) -> None:
        page = self._open_page()
        tab = page.state_supervision_tab
        self.assertEqual(tab.mode_filter.currentText(), FILTER_ALL)
        buttons = [
            button.text()
            for button in tab.findChildren(QPushButton)
        ]
        self.assertIn("Nový státní dozor", buttons)
        self.assertIn("Upravit", buttons)
        self.assertNotIn("Odstranit", buttons)
        self.assertNotIn("Otevřít", buttons)
        self.assertFalse(tab.edit_btn.isEnabled())
        page.close()

    def test_03_closed_and_cancelled_visible(self) -> None:
        active = self._create()
        closed = self._create(status=STATUS_CLOSED)
        cancelled = self._create(status=STATUS_CANCELLED)
        page = self._open_page()
        tab = page.state_supervision_tab
        tab.text_filter.search_edit.setText(self.marker)
        ids = {
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        }
        self.assertIn(active.id, ids)
        self.assertIn(closed.id, ids)
        self.assertIn(cancelled.id, ids)
        page.close()

    def test_04_exact_columns_without_file_number_or_priority(self) -> None:
        self._create(
            file_number="ČJ/2026/9",
            subject="Předmět skrytý",
            result="Bez závad",
        )
        page = self._open_page()
        tab = page.state_supervision_tab
        headers = [
            tab.table.horizontalHeaderItem(column).text()
            for column in range(tab.table.columnCount())
        ]
        self.assertEqual(headers, COLUMN_HEADERS)
        joined = " ".join(
            tab.table.item(row, column).text()
            for row in range(tab.table.rowCount())
            for column in range(tab.table.columnCount())
        )
        self.assertNotIn("ČJ/2026/9", joined)
        self.assertNotIn("Kritická", joined)
        self.assertNotIn("Priorita", " ".join(headers))
        self.assertNotIn("Číslo jednací", " ".join(headers))
        page.close()

    def test_05_status_colors_and_tooltips(self) -> None:
        expected = {
            STATUS_ANNOUNCED: STATUS_WAITING_BG,
            STATUS_PREPARATION: STATUS_WARNING_BG,
            STATUS_IN_PROGRESS: STATUS_IN_PROGRESS_BG,
            STATUS_WAITING_PROTOCOL: STATUS_WAITING_BG,
            STATUS_OBJECTIONS_PERIOD: STATUS_IN_PROGRESS_BG,
            STATUS_MEASURES_IN_PROGRESS: STATUS_IN_PROGRESS_BG,
            STATUS_WAITING_AUTHORITY_CONFIRMATION: STATUS_WAITING_BG,
            STATUS_CLOSED: STATUS_DONE_BG,
            STATUS_CANCELLED: STATUS_NEUTRAL_BG,
        }
        created = {
            status: self._create(status=status, authority_name=f"{status} {self.marker}")
            for status in STATE_SUPERVISION_STATUS_ORDER
        }
        page = self._open_page()
        tab = page.state_supervision_tab
        self.assertIsInstance(tab.table.itemDelegateForColumn(COL_STATUS), StatusCubeDelegate)
        by_id = {}
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, COL_STATUS)
            by_id[item.data(Qt.ItemDataRole.UserRole)] = item
        for status, record in created.items():
            item = by_id[record.id]
            self.assertEqual(item.text(), "")
            self.assertEqual(item.background().color(), QColor(expected[status]))
            tooltip = item.toolTip()
            self.assertIn(STATE_SUPERVISION_STATUS_LABELS[status], tooltip)
            self.assertIn(STATE_SUPERVISION_STATUS_HINTS[status], tooltip)
            self.assertEqual(tooltip, status_cube_tooltip(status))
            tab.table.selectRow(item.row())
            self.assertEqual(item.background().color(), QColor(expected[status]))
        self.assertEqual(STATUS_CUBE_COLORS, expected)
        white = QColor("#ffffff")
        blue = QColor(STATUS_WAITING_BG)
        self.assertGreater(abs(blue.lightness() - white.lightness()), 20)
        self.assertNotEqual(blue, QColor(STATUS_WARNING_BG))
        self.assertNotEqual(blue, QColor(STATUS_IN_PROGRESS_BG))
        page.close()

    def test_06_hint_is_gray(self) -> None:
        page = self._open_page()
        tab = page.state_supervision_tab
        self.assertEqual(tab.hint_label.text(), STATUS_CUBE_HINT)
        self.assertIn("color: #666", tab.hint_label.styleSheet())
        page.close()

    def test_07_start_end_empty_and_result_tooltip(self) -> None:
        actual = datetime(2026, 3, 10, 9, 15)
        planned = datetime(2026, 4, 1, 8, 0)
        closed_at = datetime(2026, 5, 20, 12, 0)
        record = self._create(
            started_at=actual,
            planned_start_at=planned,
            ended_at=None,
            closed_at=closed_at,
            workplace_id=self.workplace.id,
            result="Velmi dlouhý výsledek kontroly s podrobným popisem nálezů " * 3,
        )
        empty = self._create(
            authority_name=f"Prázdná {self.marker}",
            planned_start_at=planned,
        )
        page = self._open_page()
        tab = page.state_supervision_tab
        by_id = {}
        for row in range(tab.table.rowCount()):
            by_id[tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)] = row

        actual_row = by_id[record.id]
        self.assertEqual(
            tab.table.item(actual_row, COL_STARTED).text(),
            format_supervision_date(actual),
        )
        self.assertIn(
            "Skutečné zahájení:",
            tab.table.item(actual_row, COL_STARTED).toolTip(),
        )
        self.assertNotIn(
            "Plánované zahájení:",
            tab.table.item(actual_row, COL_STARTED).toolTip(),
        )
        self.assertEqual(tab.table.item(actual_row, COL_ENDED).text(), EMPTY_VALUE)
        self.assertEqual(
            tab.table.item(actual_row, COL_WORKPLACE).text(),
            self.workplace.name,
        )
        result_item = tab.table.item(actual_row, COL_RESULT)
        self.assertEqual(result_item.text(), record.result)
        self.assertIn("Velmi dlouhý výsledek", result_item.toolTip())
        self.assertEqual(tab.table.textElideMode(), Qt.TextElideMode.ElideRight)
        tab.table.setColumnWidth(COL_RESULT, 80)
        self.assertTrue(table_cell_text_is_elided(tab.table, actual_row, COL_RESULT))

        empty_row = by_id[empty.id]
        self.assertEqual(
            tab.table.item(empty_row, COL_STARTED).text(),
            format_supervision_date(planned),
        )
        self.assertIn(
            "Plánované zahájení:",
            tab.table.item(empty_row, COL_STARTED).toolTip(),
        )
        self.assertEqual(tab.table.item(empty_row, COL_WORKPLACE).text(), EMPTY_VALUE)
        self.assertEqual(tab.table.item(empty_row, COL_ENDED).text(), EMPTY_VALUE)
        self.assertEqual(tab.table.item(empty_row, COL_RESULT).text(), EMPTY_VALUE)
        page.close()

    def test_08_mode_year_authority_workplace_status_filters(self) -> None:
        active = self._create(
            started_at=datetime(2025, 2, 1, 8, 0),
            workplace_id=self.workplace.id,
        )
        closed = self._create(
            authority_name=f"SÚIP {self.marker}",
            status=STATUS_CLOSED,
            started_at=datetime(2026, 1, 10, 8, 0),
        )
        cancelled = self._create(
            status=STATUS_CANCELLED,
            started_at=datetime(2026, 3, 1, 8, 0),
        )
        page = self._open_page()
        tab = page.state_supervision_tab
        tab.text_filter.search_edit.setText(self.marker)

        def visible_ids() -> set[int]:
            return {
                tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
                for row in range(tab.table.rowCount())
                if not tab.table.isRowHidden(row)
            }

        tab.mode_filter.setCurrentText(FILTER_MODE_ACTIVE)
        self.assertIn(active.id, visible_ids())
        self.assertNotIn(closed.id, visible_ids())
        self.assertNotIn(cancelled.id, visible_ids())

        tab.mode_filter.setCurrentText(FILTER_MODE_CLOSED)
        self.assertEqual(visible_ids(), {closed.id})

        tab.mode_filter.setCurrentText(FILTER_ALL)
        tab.status_filter.setCurrentText(STATE_SUPERVISION_STATUS_LABELS[STATUS_CANCELLED])
        self.assertEqual(visible_ids(), {cancelled.id})

        tab.status_filter.setCurrentText(FILTER_ALL)
        tab.year_filter.setCurrentText("2025")
        self.assertEqual(visible_ids(), {active.id})

        tab.year_filter.setCurrentText(FILTER_ALL)
        tab.authority_filter.setCurrentText(f"SÚIP {self.marker}")
        self.assertEqual(visible_ids(), {closed.id})

        tab.authority_filter.setCurrentText(FILTER_ALL)
        tab.workplace_filter.setCurrentText(self.workplace.name)
        self.assertEqual(visible_ids(), {active.id})
        page.close()

    def test_09_search_and_counter(self) -> None:
        first = self._create(authority_name=f"Hledaná {self.marker}")
        self._create(authority_name=f"Jiná {self.marker}")
        page = self._open_page()
        tab = page.state_supervision_tab
        tab.text_filter.search_edit.setText(f"Hledaná {self.marker}")
        visible = [
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        ]
        self.assertEqual(visible, [first.id])
        self.assertIn("Zobrazeno: 1 /", tab.text_filter.count_label.text())
        page.close()

    def test_10_default_and_typed_date_sorting(self) -> None:
        old = self._create(started_at=datetime(2024, 1, 1, 8, 0))
        planned = self._create(planned_start_at=datetime(2025, 6, 1, 8, 0))
        newest = self._create()
        page = self._open_page()
        tab = page.state_supervision_tab
        tab.text_filter.search_edit.setText(self.marker)
        order = [
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        ]
        self.assertEqual(order, [newest.id, planned.id, old.id])

        tab.table.sortItems(COL_STARTED, Qt.SortOrder.AscendingOrder)
        sorted_ids = [
            tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        ]
        self.assertEqual(sorted_ids, [old.id, planned.id, newest.id])
        page.close()

    def test_11_empty_vs_filter_and_load_error(self) -> None:
        with patch(
            "moduly.statni_dozor.ui.state_supervision_tab.state_supervision_service.list_supervisions",
            return_value=[],
        ):
            empty_tab = StateSupervisionTab()
            self.assertEqual(empty_tab.empty_label.text(), EMPTY_STATE_NONE)
            self.assertFalse(empty_tab.empty_label.isHidden())
            self.assertTrue(empty_tab.table.isHidden())
            empty_tab.close()

        self._create()
        page = self._open_page()
        tab = page.state_supervision_tab
        tab.mode_filter.setCurrentText(FILTER_MODE_CLOSED)
        tab.authority_filter.setCurrentText(f"OIP {self.marker}")
        self.assertFalse(tab.empty_label.isHidden())
        self.assertEqual(tab.empty_label.text(), EMPTY_STATE_FILTER)
        self.assertTrue(tab.table.isHidden())
        page.close()

        with patch(
            "moduly.statni_dozor.ui.state_supervision_tab.state_supervision_service.list_supervisions",
            side_effect=RuntimeError("umělá chyba"),
        ):
            with self.assertLogs(
                "moduly.statni_dozor.ui.state_supervision_tab",
                level="ERROR",
            ):
                broken = AgendaPage()
            self.assertEqual(
                broken.state_supervision_tab.empty_label.text(),
                LOAD_ERROR_TEXT,
            )
            self.assertFalse(broken.state_supervision_tab.empty_label.isHidden())
            self.assertEqual(broken.tabs.tabText(0), TAB_TASKS_MEETINGS)
            self.assertTrue(hasattr(broken, "table"))
            self.assertTrue(hasattr(broken, "periodic_tab"))
            broken.refresh()
            broken.periodic_tab.refresh()
            broken.close()

    def test_12_refresh_without_db_write(self) -> None:
        self._create()
        before = _count_supervisions()
        page = self._open_page()
        page.state_supervision_tab.refresh()
        from PySide6.QtGui import QShowEvent

        page.showEvent(QShowEvent())
        page.state_supervision_tab.refresh()
        self.assertEqual(_count_supervisions(), before)
        self.assertNotIn(
            "statni_dozor",
            inspect.getsource(agenda_service.get_items),
        )
        items = agenda_service.get_items()
        self.assertFalse(
            any(self.marker in (getattr(item, "title", "") or "") for item in items)
        )
        page.close()


if __name__ == "__main__":
    unittest.main()
