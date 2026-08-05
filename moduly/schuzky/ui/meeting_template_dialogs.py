"""Dialogy šablon událostí – uložení a výběr."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.schuzky.constants import (
    TEMPLATE_BTN_USE,
    TEMPLATE_COL_ITEMS,
    TEMPLATE_COL_NAME,
    TEMPLATE_COL_TYPE,
    TEMPLATE_EMPTY_LIST,
    TEMPLATE_NAME_LABEL,
    TEMPLATE_NAME_REQUIRED,
    TEMPLATE_PICK_DIALOG_TITLE,
    TEMPLATE_SAVE_DIALOG_TITLE,
)
from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service


class SaveMeetingTemplateDialog(QDialog):
    def __init__(self, parent=None, *, suggested_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle(TEMPLATE_SAVE_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(420, 120)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Název šablony")
        if suggested_name:
            self.name_edit.setText(suggested_name)
            self.name_edit.selectAll()
        form.addRow(TEMPLATE_NAME_LABEL, self.name_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self, is_new=True)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def template_name(self) -> str:
        return self.name_edit.text().strip()

    def _on_accept(self) -> None:
        if not self.template_name():
            QMessageBox.warning(self, TEMPLATE_SAVE_DIALOG_TITLE, TEMPLATE_NAME_REQUIRED)
            self.name_edit.setFocus()
            return
        self.accept()


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
