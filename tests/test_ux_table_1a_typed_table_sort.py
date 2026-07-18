"""UX-TABLE-1a – testy společného typovaného řazení tabulek."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from core.widgets.typed_table_sort import (
    TypedSortTableWidgetItem,
    compare_typed_sort_values,
    create_typed_item,
    enable_typed_sorting,
    typed_bool,
    typed_date,
    typed_datetime,
    typed_empty,
    typed_float,
    typed_int,
    typed_status,
    typed_text,
)


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _column_texts(table: QTableWidget, column: int = 0) -> list[str]:
    return [table.item(row, column).text() for row in range(table.rowCount())]


def _make_table(rows: list[tuple[str, object]], *, stable: bool = True) -> QTableWidget:
    table = QTableWidget(len(rows), 1)
    enable_typed_sorting(table)
    table.setSortingEnabled(False)
    for index, (display, sort_value) in enumerate(rows):
        kwargs = {"stable_id": index} if stable else {}
        table.setItem(index, 0, create_typed_item(display, sort_value, **kwargs))
    table.setSortingEnabled(True)
    return table


class TypedTableSortUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def test_czech_order_including_ch(self) -> None:
        table = _make_table(
            [
                ("Chalupa", typed_text("Chalupa")),
                ("Cibule", typed_text("Cibule")),
                ("Hrášek", typed_text("Hrášek")),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table), ["Cibule", "Hrášek", "Chalupa"])

    def test_natural_text_numbers(self) -> None:
        table = _make_table(
            [
                ("položka 10", typed_text("položka 10")),
                ("položka 2", typed_text("položka 2")),
                ("položka 1", typed_text("položka 1")),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table),
            ["položka 1", "položka 2", "položka 10"],
        )

    def test_integers(self) -> None:
        table = _make_table(
            [
                ("10", typed_int(10)),
                ("2", typed_int(2)),
                ("1", typed_int(1)),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table), ["1", "2", "10"])

    def test_floats(self) -> None:
        table = _make_table(
            [
                ("1 250,50", typed_float(1250.5)),
                ("10,5", typed_float(10.5)),
                ("2,25", typed_float(2.25)),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table), ["2,25", "10,5", "1 250,50"])

    def test_date_uses_real_value_not_display(self) -> None:
        table = _make_table(
            [
                ("01.02.2026", typed_date(date(2026, 2, 1))),
                ("15.01.2026", typed_date(date(2026, 1, 15))),
                ("10.12.2025", typed_date(date(2025, 12, 10))),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        # Lexikograficky by "01.02" bylo před "10.12"; chronologicky ne.
        self.assertEqual(
            _column_texts(table),
            ["10.12.2025", "15.01.2026", "01.02.2026"],
        )

    def test_datetime(self) -> None:
        table = _make_table(
            [
                ("18.07. 14:00", typed_datetime(datetime(2026, 7, 18, 14, 0))),
                ("18.07. 09:00", typed_datetime(datetime(2026, 7, 18, 9, 0))),
                ("17.07. 20:00", typed_datetime(datetime(2026, 7, 17, 20, 0))),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table),
            ["17.07. 20:00", "18.07. 09:00", "18.07. 14:00"],
        )

    def test_boolean(self) -> None:
        table = _make_table(
            [
                ("Ano", typed_bool(True)),
                ("Ne", typed_bool(False)),
                ("Ano", typed_bool(True)),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table), ["Ne", "Ano", "Ano"])

    def test_explicit_status_order(self) -> None:
        table = _make_table(
            [
                ("Hotovo", typed_status(2)),
                ("Nové", typed_status(0)),
                ("Probíhá", typed_status(1)),
            ]
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table), ["Nové", "Probíhá", "Hotovo"])

    def test_blanks_always_last_ascending_and_descending(self) -> None:
        rows = [
            ("B", typed_text("B")),
            ("", typed_empty()),
            ("A", typed_text("A")),
            ("   ", typed_text("   ")),
            ("—", typed_empty()),
        ]
        table = _make_table(rows)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        texts = _column_texts(table)
        self.assertEqual(texts[:2], ["A", "B"])
        self.assertEqual(set(texts[2:]), {"", "   ", "—"})

        table.sortItems(0, Qt.SortOrder.DescendingOrder)
        texts = _column_texts(table)
        self.assertEqual(texts[:2], ["B", "A"])
        self.assertEqual(set(texts[2:]), {"", "   ", "—"})

    def test_compare_helper_blanks_last_both_directions(self) -> None:
        empty = typed_empty()
        value = typed_text("A")
        self.assertEqual(compare_typed_sort_values(empty, value, ascending=True), 1)
        self.assertEqual(compare_typed_sort_values(value, empty, ascending=True), -1)
        self.assertEqual(compare_typed_sort_values(empty, value, ascending=False), -1)
        self.assertEqual(compare_typed_sort_values(value, empty, ascending=False), 1)

    def test_header_click_toggles_direction(self) -> None:
        table = _make_table(
            [
                ("C", typed_text("C")),
                ("A", typed_text("A")),
                ("B", typed_text("B")),
            ]
        )
        header = table.horizontalHeader()
        # První aktivace sloupce → vzestupně (standard Qt).
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table), ["A", "B", "C"])
        self.assertEqual(header.sortIndicatorOrder(), Qt.SortOrder.AscendingOrder)

        # Druhý klik / sestupně.
        header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        table.sortItems(0, Qt.SortOrder.DescendingOrder)
        self.assertEqual(_column_texts(table), ["C", "B", "A"])
        self.assertEqual(header.sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)

    def test_equal_keys_are_stable(self) -> None:
        table = _make_table(
            [
                ("stejné-0", typed_text("stejné")),
                ("stejné-1", typed_text("stejné")),
                ("stejné-2", typed_text("stejné")),
            ],
            stable=True,
        )
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table),
            ["stejné-0", "stejné-1", "stejné-2"],
        )
        table.sortItems(0, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            _column_texts(table),
            ["stejné-0", "stejné-1", "stejné-2"],
        )

    def test_create_typed_item_is_typed_subclass(self) -> None:
        item = create_typed_item("x", typed_int(1), stable_id=5)
        self.assertIsInstance(item, TypedSortTableWidgetItem)


if __name__ == "__main__":
    unittest.main()
