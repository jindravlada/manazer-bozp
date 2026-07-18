from datetime import date

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS

DOCUMENT_TYPE_ORDER = tuple(DOCUMENT_TYPE_LABELS.keys())


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
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _format_included_in_processes(value: bool) -> str:
    return "ANO" if value else "NE"


class LegalDocumentTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(9)
        self.setHorizontalHeaderLabels([
            "ID",
            "Typ",
            "Číslo",
            "Rok",
            "Název",
            "Zkratka",
            "Účinnost od",
            "Zahrnuto v procesech",
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
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        for column in (1, 2, 3, 5, 6, 7, 8):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(1, 130)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(5, 120)
        self.setColumnWidth(6, 110)
        self.setColumnWidth(7, 150)
        self.setColumnWidth(8, 80)

        enable_typed_sorting(self)

    def load_documents(self, documents) -> None:
        with sorting_paused(self):
            self.setRowCount(len(documents))

            for row, document in enumerate(documents):
                record_id = int(document.id)
                self.setItem(
                    row,
                    0,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                type_label = DOCUMENT_TYPE_LABELS.get(document.document_type, document.document_type)
                self.setItem(
                    row,
                    1,
                    create_typed_item(
                        type_label,
                        _order_status(document.document_type, DOCUMENT_TYPE_ORDER),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    2,
                    create_typed_item(document.number, typed_text(document.number), stable_id=record_id),
                )
                self.setItem(
                    row,
                    3,
                    create_typed_item(
                        str(document.year) if document.year is not None else "",
                        typed_int(document.year),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    4,
                    create_typed_item(document.title, typed_text(document.title), stable_id=record_id),
                )
                self.setItem(
                    row,
                    5,
                    create_typed_item(
                        document.short_title,
                        typed_text(document.short_title),
                        stable_id=record_id,
                    ),
                )
                effective_from = document.effective_from or document.valid_from
                self.setItem(
                    row,
                    6,
                    create_typed_item(
                        _format_date(effective_from),
                        typed_date(effective_from),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    7,
                    create_typed_item(
                        _format_included_in_processes(document.included_in_processes),
                        typed_bool(document.included_in_processes),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    8,
                    create_typed_item(
                        "Ano" if document.active else "Ne",
                        typed_bool(document.active),
                        stable_id=record_id,
                    ),
                )

                if not document.active:
                    brush = QBrush(QColor("#f0f0f0"))
                    for column in range(self.columnCount()):
                        item = self.item(row, column)
                        if item is not None:
                            item.setBackground(brush)

    def selected_document_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
