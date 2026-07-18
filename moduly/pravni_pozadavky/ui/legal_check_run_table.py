from datetime import date, datetime

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_date,
    typed_datetime,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.pravni_pozadavky.constants import (
    CHECK_RUN_CANCELLED,
    CHECK_RUN_COMPLETED,
    CHECK_RUN_ERROR,
    CHECK_RUN_IN_PROGRESS,
    CHECK_RUN_NEW,
    CHECK_RUN_STATUS_LABELS,
)

CHECK_RUN_ORDER = (
    CHECK_RUN_NEW,
    CHECK_RUN_IN_PROGRESS,
    CHECK_RUN_COMPLETED,
    CHECK_RUN_ERROR,
    CHECK_RUN_CANCELLED,
)


def _order_status(value: str, order: tuple[str, ...]):
    if not value:
        return typed_empty()
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _date_sort_value(value):
    if isinstance(value, datetime):
        return typed_datetime(value)
    return typed_date(value)


class LegalCheckRunTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "ID",
            "Název",
            "Období od",
            "Období do",
            "Datum kontroly",
            "Stav",
            "Aktivní",
        ])

        self.setColumnHidden(0, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(4, 120)
        self.setColumnWidth(5, 110)
        self.setColumnWidth(6, 80)

        enable_typed_sorting(self)

    def load_runs(self, runs) -> None:
        with sorting_paused(self):
            self.setRowCount(len(runs))

            for row, run in enumerate(runs):
                record_id = int(run.id)
                status_label = CHECK_RUN_STATUS_LABELS.get(run.status, run.status)
                self.setItem(
                    row,
                    0,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    1,
                    create_typed_item(run.title, typed_text(run.title), stable_id=record_id),
                )
                self.setItem(
                    row,
                    2,
                    create_typed_item(
                        _format_date(run.period_from),
                        typed_date(run.period_from),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    3,
                    create_typed_item(
                        _format_date(run.period_to),
                        typed_date(run.period_to),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    4,
                    create_typed_item(
                        _format_date(run.checked_at),
                        _date_sort_value(run.checked_at),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    5,
                    create_typed_item(
                        status_label,
                        _order_status(run.status, CHECK_RUN_ORDER),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    6,
                    create_typed_item(
                        "Ano" if run.active else "Ne",
                        typed_bool(run.active),
                        stable_id=record_id,
                    ),
                )

                if not run.active:
                    brush = QBrush(QColor("#f0f0f0"))
                    for column in range(self.columnCount()):
                        item = self.item(row, column)
                        if item is not None:
                            item.setBackground(brush)

    def selected_run_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
