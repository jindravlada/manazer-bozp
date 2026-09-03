"""INSPECTIONS-OVERVIEW-NUMBER-SORT-3: číselné řazení sloupce Číslo."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import event

_TMP = Path(tempfile.mkdtemp(prefix="inspections-number-sort-3-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.typed_table_sort import (
        SortKind,
        compare_typed_sort_values,
        typed_empty,
    )
    from moduly.proverky.constants import (
        INSPECTION_STATUS_FILTER_VSE,
        YEAR_FILTER_VSE,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.bozp_inspection_table import (
        COL_NUMBER,
        BozpInspectionTable,
        inspection_number_sort_value,
    )
    from moduly.proverky.ui.proverky_page import ProverkyPage


def _row(
    *,
    inspection_id: int,
    number: str,
    total: int = 0,
    workplace: str = "Provoz",
    inspection_date: date | None = None,
    status: str = "Plánováno",
):
    return SimpleNamespace(
        id=inspection_id,
        number=number,
        inspection_date=inspection_date,
        workplace_name=workplace,
        findings_total_count=total,
        zavady_count=total,
        nedostatky_count=0,
        poruseni_predpisu_count=0,
        neshody_count=0,
        pozorovani_count=0,
        zjisteni_count=0,
        pkz_count=0,
        ostatni_count=0,
        status=status,
    )


def _numbers(table: BozpInspectionTable) -> list[str]:
    return [table.item(row, COL_NUMBER).text() for row in range(table.rowCount())]


def _ids(table: BozpInspectionTable) -> list[int]:
    return [int(table.item(row, 0).text()) for row in range(table.rowCount())]


class InspectionsOverviewNumberSort3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)

    def _prepare_page(self) -> ProverkyPage:
        page = ProverkyPage()
        page.status_filter.setCurrentText(INSPECTION_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        return page

    def _set_number(self, inspection, number: str):
        inspection.number = number
        return bozp_inspection_service.repository.update(inspection)

    def test_01_numeric_order_within_year(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                _row(inspection_id=30, number="10/2026"),
                _row(inspection_id=10, number="1/2026"),
                _row(inspection_id=20, number="2/2026"),
            ]
        )
        self.assertEqual(_numbers(table), ["1/2026", "2/2026", "10/2026"])

    def test_02_year_2026_before_2027(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                _row(inspection_id=2, number="1/2027"),
                _row(inspection_id=1, number="10/2026"),
            ]
        )
        self.assertEqual(_numbers(table), ["10/2026", "1/2027"])

    def test_03_years_do_not_interleave(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                _row(inspection_id=4, number="2/2027"),
                _row(inspection_id=1, number="1/2026"),
                _row(inspection_id=3, number="1/2027"),
                _row(inspection_id=2, number="2/2026"),
            ]
        )
        self.assertEqual(_numbers(table), ["1/2026", "2/2026", "1/2027", "2/2027"])
        self.assertNotEqual(_numbers(table), ["1/2026", "1/2027", "2/2026", "2/2027"])

    def test_04_descending_reverses_year_and_sequence(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                _row(inspection_id=1, number="1/2026"),
                _row(inspection_id=2, number="2/2026"),
                _row(inspection_id=3, number="10/2026"),
                _row(inspection_id=4, number="1/2027"),
                _row(inspection_id=5, number="2/2027"),
            ]
        )
        table.sortItems(COL_NUMBER, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            _numbers(table),
            ["2/2027", "1/2027", "10/2026", "2/2026", "1/2026"],
        )

    def test_05_refresh_keeps_default_number_order(self) -> None:
        first = bozp_inspection_service.create_inspection(year=2026, workplace_name="A")
        second = bozp_inspection_service.create_inspection(year=2026, workplace_name="B")
        third = bozp_inspection_service.create_inspection(year=2027, workplace_name="C")
        self._set_number(first, "10/2026")
        self._set_number(second, "1/2026")
        self._set_number(third, "1/2027")

        page = self._prepare_page()
        try:
            self.assertEqual(_numbers(page.table), ["1/2026", "10/2026", "1/2027"])
            page.refresh()
            self.assertEqual(_numbers(page.table), ["1/2026", "10/2026", "1/2027"])
            created = bozp_inspection_service.create_inspection(
                year=2026,
                workplace_name="D",
            )
            self._set_number(created, "2/2026")
            page.refresh()
            self.assertEqual(_numbers(page.table), ["1/2026", "2/2026", "10/2026", "1/2027"])
            bozp_inspection_service.delete_inspection(created.id)
            page.refresh()
            self.assertEqual(_numbers(page.table), ["1/2026", "10/2026", "1/2027"])
        finally:
            page.close()
            page.deleteLater()

    def test_06_invalid_and_empty_numbers_do_not_crash(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                _row(inspection_id=4, number="—"),
                _row(inspection_id=1, number="2/2026"),
                _row(inspection_id=2, number="historie"),
                _row(inspection_id=5, number="1/2026"),
            ]
        )
        self.assertEqual(_numbers(table), ["1/2026", "2/2026", "historie", "—"])

        empty = inspection_number_sort_value("")
        invalid = inspection_number_sort_value("historie")
        dash = inspection_number_sort_value("—")
        none_value = inspection_number_sort_value(None)
        self.assertEqual(empty.kind, SortKind.EMPTY)
        self.assertEqual(invalid.kind, SortKind.EMPTY)
        self.assertEqual(dash.kind, SortKind.EMPTY)
        self.assertEqual(none_value.kind, SortKind.EMPTY)
        self.assertEqual(
            compare_typed_sort_values(empty, typed_empty(), ascending=True),
            0,
        )

    def test_07_double_click_opens_correct_inspection_after_sort(self) -> None:
        low = bozp_inspection_service.create_inspection(year=2026, workplace_name="Nízký")
        high = bozp_inspection_service.create_inspection(year=2026, workplace_name="Vysoký")
        self._set_number(low, "10/2026")
        self._set_number(high, "1/2026")

        page = self._prepare_page()
        try:
            self.assertEqual(_numbers(page.table), ["1/2026", "10/2026"])
            target_row = 0
            selection_model = page.table.selectionModel()
            selection_model.clearSelection()
            flags = (
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows
            )
            selection_model.select(page.table.model().index(target_row, 0), flags)
            with patch.object(page, "open_inspection") as open_mock:
                page.table.doubleClicked.emit(page.table.model().index(target_row, 0))
                open_mock.assert_called_once_with(high.id)
        finally:
            page.close()
            page.deleteLater()

    def test_08_other_columns_keep_typed_sorting(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                _row(inspection_id=1, number="1/2026", total=10, workplace="Chalupa"),
                _row(inspection_id=2, number="2/2026", total=2, workplace="Cibule"),
            ]
        )
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual([table.item(row, 4).text() for row in range(2)], ["2", "10"])
        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            [table.item(row, 3).text() for row in range(2)],
            ["Cibule", "Chalupa"],
        )

    def test_09_sorting_does_not_write_to_db(self) -> None:
        bozp_inspection_service.create_inspection(year=2026, workplace_name="A")
        bozp_inspection_service.create_inspection(year=2026, workplace_name="B")
        page = self._prepare_page()
        engine = session_module.engine
        statements: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            statements.append(statement.lstrip().upper())

        event.listen(engine, "before_cursor_execute", _capture)
        try:
            page.table.sortItems(COL_NUMBER, Qt.SortOrder.DescendingOrder)
            page.table.sortItems(COL_NUMBER, Qt.SortOrder.AscendingOrder)
        finally:
            event.remove(engine, "before_cursor_execute", _capture)
            page.close()
            page.deleteLater()

        writes = [
            statement
            for statement in statements
            if statement.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
        ]
        self.assertEqual(writes, [])

    def test_10_composite_key_is_year_then_sequence(self) -> None:
        first = inspection_number_sort_value("1/2026")
        tenth = inspection_number_sort_value("10/2026")
        next_year = inspection_number_sort_value("1/2027")
        self.assertEqual(first.kind, SortKind.INT)
        self.assertEqual(first.payload, 2026 * 1_000_000 + 1)
        self.assertEqual(tenth.payload, 2026 * 1_000_000 + 10)
        self.assertEqual(next_year.payload, 2027 * 1_000_000 + 1)
        self.assertLess(first.payload, tenth.payload)
        self.assertLess(tenth.payload, next_year.payload)


if __name__ == "__main__":
    unittest.main()
