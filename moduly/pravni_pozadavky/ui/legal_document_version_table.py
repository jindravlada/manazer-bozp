from datetime import date

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_date,
    typed_int,
    typed_text,
)


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalDocumentVersionTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "ID",
            "Verze",
            "Účinnost od",
            "Účinnost do",
            "Publikováno",
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
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(2, 110)
        self.setColumnWidth(3, 110)
        self.setColumnWidth(4, 110)
        self.setColumnWidth(5, 80)

        enable_typed_sorting(self)

    def load_versions(self, versions) -> None:
        with sorting_paused(self):
            self.setRowCount(len(versions))

            for row, version in enumerate(versions):
                record_id = int(version.id)
                self.setItem(
                    row,
                    0,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    1,
                    create_typed_item(
                        version.version_name,
                        typed_text(version.version_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    2,
                    create_typed_item(
                        _format_date(version.effective_from),
                        typed_date(version.effective_from),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    3,
                    create_typed_item(
                        _format_date(version.effective_to),
                        typed_date(version.effective_to),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    4,
                    create_typed_item(
                        _format_date(version.publication_date),
                        typed_date(version.publication_date),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    5,
                    create_typed_item(
                        "Ano" if version.active else "Ne",
                        typed_bool(version.active),
                        stable_id=record_id,
                    ),
                )

                if not version.active:
                    brush = QBrush(QColor("#f0f0f0"))
                    for column in range(self.columnCount()):
                        item = self.item(row, column)
                        if item is not None:
                            item.setBackground(brush)

    def selected_version_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
