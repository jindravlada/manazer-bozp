from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    ATT_COL_ACTIVE,
    ATT_COL_DESCRIPTION,
    ATT_COL_FILENAME,
    ATT_COL_ID,
    ATT_COL_TYPE,
    ATT_COLUMN_COUNT,
    ATTACHMENT_TABLE_HEADERS,
    ATTACHMENT_TYPE_LABELS,
)


class CoordinationAttachmentTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(ATT_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(ATTACHMENT_TABLE_HEADERS)
        self.setColumnHidden(ATT_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_attachments(self, attachments) -> None:
        with sorting_paused(self):
            self.setRowCount(len(attachments))
            for row, item in enumerate(attachments):
                record_id = int(item.id)
                type_label = ATTACHMENT_TYPE_LABELS.get(
                    item.attachment_type,
                    item.attachment_type,
                )
                self.setItem(
                    row,
                    ATT_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ATT_COL_FILENAME,
                    create_typed_item(
                        item.original_filename or "",
                        typed_text(item.original_filename),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ATT_COL_TYPE,
                    create_typed_item(
                        type_label,
                        typed_text(type_label),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ATT_COL_DESCRIPTION,
                    create_typed_item(
                        item.description or "",
                        typed_text(item.description),
                        stable_id=record_id,
                    ),
                )
                active_item = create_typed_item(
                    "Ano" if item.active else "Ne",
                    typed_bool(bool(item.active)),
                    stable_id=record_id,
                )
                if not item.active:
                    active_item.setData(Qt.ItemDataRole.UserRole + 1, False)
                self.setItem(row, ATT_COL_ACTIVE, active_item)

    def selected_attachment_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), ATT_COL_ID)
        if item is None:
            return None
        return int(item.text())
