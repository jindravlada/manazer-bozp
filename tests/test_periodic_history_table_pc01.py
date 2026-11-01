"""PC-01: šířka tabulky historie periodické činnosti."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QHeaderView, QSizePolicy

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.periodicke_cinnosti.constants import (
        HISTORY_COL_NOTE,
        HISTORY_COL_PERFORMED,
        HISTORY_COL_PERFORMER,
        HISTORY_COL_PLANNED,
        HISTORY_HEADERS,
        TAB_HISTORY,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )

_DATE_SAMPLE = "31.12.2026 23:59"
_NAME_SAMPLE = "Jméno Příjmení Pracovníka"
_LONG_NOTE = (
    "Kontrola hasicích přístrojů na všech podlažích výrobní haly byla dokončena "
    "bez závad. Doklady jsou uložené u vedoucího směny a další termín zůstává "
    "v plánu periodických činností beze změny rozsahu."
)


class PeriodicHistoryTablePc01TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        dialog = getattr(self, "dialog", None)
        if dialog is not None:
            dialog._editor._closing = True
            dialog.close()

    def _activity(self, title: str):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=date(2026, 6, 1),
        )

    def _show_history(self, dialog: PeriodicActivityDialog, width: int, height: int) -> None:
        dialog.resize(width, height)
        history_index = next(
            index
            for index in range(dialog.tabs.count())
            if dialog.tabs.tabText(index) == TAB_HISTORY
        )
        dialog.tabs.setCurrentIndex(history_index)
        dialog.show()
        QApplication.processEvents()

    def test_empty_history_keeps_column_layout(self) -> None:
        self.dialog = PeriodicActivityDialog()
        self._show_history(self.dialog, 720, 640)
        table = self.dialog.history_table
        self.assertTrue(self.dialog.history_empty.isVisible())
        self.assertFalse(table.isVisible())
        self.assertEqual(table.rowCount(), 0)
        self.assertEqual(
            [table.horizontalHeaderItem(column).text() for column in range(table.columnCount())],
            list(HISTORY_HEADERS),
        )
        header = table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(HISTORY_COL_NOTE),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (HISTORY_COL_PLANNED, HISTORY_COL_PERFORMED, HISTORY_COL_PERFORMER):
            self.assertEqual(header.sectionResizeMode(column), QHeaderView.ResizeMode.Interactive)
        self.assertGreaterEqual(table.columnWidth(HISTORY_COL_PLANNED), self._date_width(table))
        self.assertGreaterEqual(table.columnWidth(HISTORY_COL_PERFORMED), self._date_width(table))
        self.assertGreaterEqual(table.columnWidth(HISTORY_COL_PERFORMER), self._name_width(table))
        self.assertEqual(
            table.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding,
        )
        page = self.dialog.tabs.widget(1).widget()
        margins = page.layout().contentsMargins()
        self.assertGreaterEqual(margins.left(), 6)
        self.assertGreaterEqual(margins.right(), 6)

    def test_one_record_stays_readable(self) -> None:
        activity = self._activity("Jedno provedení")
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            performed_by_name="Jana Svobodová",
            result_note="Provedeno",
        )
        activity = periodic_activity_service.get_by_id(activity.id)
        self.dialog = PeriodicActivityDialog(activity=activity)
        self._show_history(self.dialog, 900, 640)
        table = self.dialog.history_table
        self.assertEqual(table.rowCount(), 1)
        self.assertEqual(table.item(0, HISTORY_COL_PLANNED).text(), "01.06.2026")
        self.assertEqual(table.item(0, HISTORY_COL_PERFORMED).text(), "15.05.2026")
        self.assertEqual(table.item(0, HISTORY_COL_PERFORMER).text(), "Jana Svobodová")
        self.assertEqual(table.item(0, HISTORY_COL_NOTE).text(), "Provedeno")
        self.assertEqual(table.item(0, HISTORY_COL_NOTE).toolTip(), "")
        self.assertGreaterEqual(table.rowHeight(0), table.fontMetrics().height())
        self.assertGreaterEqual(
            table.horizontalHeader().height(),
            table.horizontalHeader().fontMetrics().height(),
        )
        self._assert_table_fills_page(self.dialog)

    def test_several_records_keep_order_and_long_note_tooltip(self) -> None:
        activity = self._activity("Více provedení")
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            performed_by_name="Jana Svobodová",
            result_note="Provedeno",
        )
        activity = periodic_activity_service.get_by_id(activity.id)
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 6, 20),
            performed_by_name=_NAME_SAMPLE,
            result_note=_LONG_NOTE,
        )
        activity = periodic_activity_service.get_by_id(activity.id)
        self.dialog = PeriodicActivityDialog(activity=activity)
        self._show_history(self.dialog, 640, 560)
        table = self.dialog.history_table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, HISTORY_COL_PERFORMED).text(), "20.06.2026")
        self.assertEqual(table.item(1, HISTORY_COL_PERFORMED).text(), "15.05.2026")
        self.assertEqual(table.item(0, HISTORY_COL_PERFORMER).text(), _NAME_SAMPLE)
        self.assertEqual(table.item(0, HISTORY_COL_NOTE).text(), _LONG_NOTE)
        self.assertIn(_LONG_NOTE.split()[0], table.item(0, HISTORY_COL_NOTE).toolTip())
        self.assertEqual(" ".join(table.item(0, HISTORY_COL_NOTE).toolTip().split()), _LONG_NOTE)
        self.assertEqual(table.item(1, HISTORY_COL_NOTE).toolTip(), "")
        narrow_note = table.columnWidth(HISTORY_COL_NOTE)
        planned = table.columnWidth(HISTORY_COL_PLANNED)
        performed = table.columnWidth(HISTORY_COL_PERFORMED)
        performer = table.columnWidth(HISTORY_COL_PERFORMER)

        self._show_history(self.dialog, 800, 700)
        self.assertGreater(table.columnWidth(HISTORY_COL_NOTE), narrow_note)
        self.assertGreaterEqual(table.columnWidth(HISTORY_COL_PLANNED), planned)
        self.assertGreaterEqual(table.columnWidth(HISTORY_COL_PERFORMED), performed)
        self.assertGreaterEqual(table.columnWidth(HISTORY_COL_PERFORMER), performer)
        self.assertEqual(" ".join(table.item(0, HISTORY_COL_NOTE).toolTip().split()), _LONG_NOTE)
        self._assert_table_fills_page(self.dialog)

    def _date_width(self, table) -> int:
        metrics = table.fontMetrics()
        return metrics.horizontalAdvance(_DATE_SAMPLE)

    def _name_width(self, table) -> int:
        return table.fontMetrics().horizontalAdvance(_NAME_SAMPLE)

    def _assert_table_fills_page(self, dialog: PeriodicActivityDialog) -> None:
        page = dialog.tabs.currentWidget().widget()
        margins = page.layout().contentsMargins()
        table = dialog.history_table
        available = page.width() - margins.left() - margins.right()
        self.assertGreaterEqual(table.width(), available - 4)
        filled = sum(table.columnWidth(column) for column in range(table.columnCount()))
        self.assertAlmostEqual(filled, table.viewport().width(), delta=8)
