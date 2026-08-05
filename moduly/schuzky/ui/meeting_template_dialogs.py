"""Dialog výběru šablony události."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from moduly.schuzky.constants import (
    TEMPLATE_BTN_USE,
    TEMPLATE_COL_ITEMS,
    TEMPLATE_COL_NAME,
    TEMPLATE_COL_TYPE,
    TEMPLATE_EMPTY_LIST,
    TEMPLATE_PICK_DIALOG_TITLE,
)
from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service


class MeetingTemplatePickDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TEMPLATE_PICK_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(560, 360)
        self._selected_id: int | None = None

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [TEMPLATE_COL_NAME, TEMPLATE_COL_TYPE, TEMPLATE_COL_ITEMS]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._on_use)
        layout.addWidget(self.table)

        self.empty_label = QLabel(TEMPLATE_EMPTY_LIST)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        buttons = QDialogButtonBox(self)
        self.use_btn = QPushButton(TEMPLATE_BTN_USE)
        self.use_btn.setDefault(True)
        close_btn = QPushButton("Zavřít")
        buttons.addButton(self.use_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self.use_btn.clicked.connect(self._on_use)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._load()

    def selected_template_id(self) -> int | None:
        return self._selected_id

    def _load(self) -> None:
        templates = meeting_template_service.get_all()
        self.table.setRowCount(0)
        self.table.setRowCount(len(templates))
        for row, template in enumerate(templates):
            name_item = QTableWidgetItem(template.name or "")
            name_item.setData(Qt.ItemDataRole.UserRole, int(template.id))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(template.event_type or ""))
            count = meeting_template_service.agenda_item_count(template)
            self.table.setItem(row, 2, QTableWidgetItem(str(count)))
        has_rows = bool(templates)
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        self.use_btn.setEnabled(has_rows)
        if has_rows:
            self.table.selectRow(0)

    def _on_use(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return
        template_id = item.data(Qt.ItemDataRole.UserRole)
        if template_id is None:
            return
        self._selected_id = int(template_id)
        self.accept()
