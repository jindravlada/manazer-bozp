from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QMessageBox,
    QPushButton,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog
from moduly.ukoly.ui.task_table import TaskTable


class UkolyPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nové opatření")
        self.edit_btn = QPushButton("Upravit")
        self.completed_btn = QPushButton("Splněno")
        self.reopen_btn = QPushButton("Vrátit do aktivních")
        self.cancel_btn = QPushButton("Zrušit / netrvá")

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Aktivní", "Ukončené", "Vše"])
        self.status_filter.currentIndexChanged.connect(self.refresh)

        legend = QLabel("Řádky: červená = po termínu, žlutá = čeká na kontrolu, zelená = ukončeno, šedá = zrušeno")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.completed_btn)
        toolbar.addWidget(self.reopen_btn)
        toolbar.addWidget(self.cancel_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.status_filter)

        self.table = TaskTable()
        configure_table_columns(self.table, "tasks")

        self.text_filter = FilterBar(self.table)

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(legend)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_task)
        self.edit_btn.clicked.connect(self.edit_selected_task)
        self.completed_btn.clicked.connect(self.mark_completed)
        self.reopen_btn.clicked.connect(self.reopen_selected_task)
        self.cancel_btn.clicked.connect(self.cancel_selected_task)
        self.table.doubleClicked.connect(self.edit_selected_task)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clear_selection()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def refresh(self):
        tasks = task_service.get_all_tasks()
        tasks = self._filter_tasks(tasks)

        self.table.load_tasks(tasks)
        configure_table_columns(self.table, "tasks")
        self.table.clear_selection()
        self.text_filter.update_count()

    def _filter_tasks(self, tasks):
        mode = self.status_filter.currentText()

        if mode == "Aktivní":
            return [
                task for task in tasks
                if task.computed_status not in ["Ukončeno", "Zrušeno"]
            ]

        if mode == "Ukončené":
            return [
                task for task in tasks
                if task.computed_status in ["Ukončeno", "Zrušeno"]
            ]

        return tasks

    def _selected_task_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None

        return int(item.text())

    def new_task(self):
        dialog = TaskDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["title"]:
                task_service.create_task(**data)
                self.refresh()

    def edit_selected_task(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Úkoly", "Vyberte opatření.")
            return

        self.open_task(task_id)

    def open_task(self, task_id: int):
        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, "Úkoly", "Opatření nebylo nalezeno.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec():
            data = dialog.get_data()
            if data["title"]:
                task_service.update_task(task_id=task_id, **data)
                self.refresh()

    def mark_completed(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Úkoly", "Vyberte opatření.")
            return

        task_service.mark_completed(task_id)
        self.refresh()

    def reopen_selected_task(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Úkoly", "Vyberte opatření.")
            return

        answer = QMessageBox.question(
            self,
            "Vrátit opatření",
            "Vrátit vybrané opatření zpět mezi aktivní?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            task_service.reopen_task(task_id)
            self.refresh()

    def cancel_selected_task(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Úkoly", "Vyberte opatření.")
            return

        answer = QMessageBox.question(
            self,
            "Zrušit opatření",
            "Opravdu označit vybrané opatření jako zrušené / netrvá?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            task_service.cancel_task(task_id)
            self.refresh()
