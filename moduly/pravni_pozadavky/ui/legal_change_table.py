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
    CHANGE_TYPE_LABELS,
    legal_document_catalog_link_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service

CHANGE_TYPE_ORDER = tuple(CHANGE_TYPE_LABELS.keys())


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


def _document_label(change) -> str:
    document = legal_document_service.get_by_id(change.legal_document_id)
    if document is None:
        return f"Předpis #{change.legal_document_id}"
    return legal_document_catalog_link_label(document)


class LegalChangeTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "ID",
            "Datum zveřejnění",
            "Typ změny",
            "Předpis",
            "Název",
            "Vyhodnoceno",
            "Aktivní",
        ])

        self.setColumnHidden(0, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        for column in (1, 2, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(1, 120)
        self.setColumnWidth(2, 150)
        self.setColumnWidth(5, 90)
        self.setColumnWidth(6, 80)

        enable_typed_sorting(self)

    def load_changes(self, changes) -> None:
        with sorting_paused(self):
            self.setRowCount(len(changes))

            for row, change in enumerate(changes):
                record_id = int(change.id)
                change_type_label = CHANGE_TYPE_LABELS.get(change.change_type, change.change_type)
                document_label = _document_label(change)
                self.setItem(
                    row,
                    0,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    1,
                    create_typed_item(
                        _format_date(change.published_at),
                        _date_sort_value(change.published_at),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    2,
                    create_typed_item(
                        change_type_label,
                        _order_status(change.change_type, CHANGE_TYPE_ORDER),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    3,
                    create_typed_item(document_label, typed_text(document_label), stable_id=record_id),
                )
                self.setItem(
                    row,
                    4,
                    create_typed_item(change.title, typed_text(change.title), stable_id=record_id),
                )
                self.setItem(
                    row,
                    5,
                    create_typed_item(
                        "Ano" if change.evaluated else "Ne",
                        typed_bool(change.evaluated),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    6,
                    create_typed_item(
                        "Ano" if change.active else "Ne",
                        typed_bool(change.active),
                        stable_id=record_id,
                    ),
                )

                if not change.active:
                    brush = QBrush(QColor("#f0f0f0"))
                    for column in range(self.columnCount()):
                        item = self.item(row, column)
                        if item is not None:
                            item.setBackground(brush)

    def selected_change_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
