from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.sluzby.audit_service import audit_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.task_display import task_description_table_text
from moduly.ukoly.ui.task_dialog import TaskDialog


class AuditTasksWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit_id: int | None = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Úkoly lze zobrazit až po uložení auditu.")
        self.info_label.setWordWrap(True)

        toolbar = QHBoxLayout()
        self.open_btn = QPushButton("Otevřít úkol")
        self.refresh_btn = QPushButton("Obnovit")
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Název",
            "Odpovědná osoba",
            "Termín",
            "Stav",
        ])
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.content_stack = QStackedWidget()
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        self.empty_label = QLabel("Audit zatím nemá žádné úkoly.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()

        self.table_page = QWidget()
        table_layout = QVBoxLayout(self.table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)

        self.content_stack.addWidget(self.empty_page)
        self.content_stack.addWidget(self.table_page)

        layout.addWidget(self.info_label)
        layout.addLayout(toolbar)
        layout.addWidget(self.content_stack, 1)

        self.open_btn.clicked.connect(self.open_selected_task)
        self.refresh_btn.clicked.connect(self.refresh)
        self.table.doubleClicked.connect(self.open_selected_task)

        self._update_state()

    def set_audit_id(self, audit_id: int | None) -> None:
        self.audit_id = audit_id
        self.refresh()
        self._update_state()

    def refresh(self) -> None:
        tasks = []
        if self.audit_id is not None:
            tasks = audit_service.get_tasks_for_audit(self.audit_id)

        self.content_stack.setCurrentIndex(1 if tasks else 0)
        self.empty_label.setText(
            "Audit zatím nemá žádné úkoly."
            if self.audit_id is not None
            else "Úkoly lze zobrazit až po uložení auditu."
        )

        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                str(task.id),
                task_description_table_text(task),
                task.responsible_person or "—",
                "" if task.due_date is None else task.due_date.strftime("%d.%m.%Y"),
                task.computed_status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.table.setItem(row, column, item)

    def _update_state(self) -> None:
        enabled = self.audit_id is not None
        self.info_label.setVisible(not enabled)
        self.open_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    def _selected_task_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def open_selected_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Úkoly", "Vyberte úkol.")
            return

        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, "Úkoly", "Úkol nebyl nalezen.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if data["title"]:
                task_service.update_task(task_id=task_id, **data)
            self.refresh()
