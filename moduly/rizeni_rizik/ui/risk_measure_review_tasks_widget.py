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
    QVBoxLayout,
    QWidget,
)

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.rizeni_rizik.constants import RISK_MEASURE_REVIEW_TASKS_TITLE
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    RiskMeasureReviewError,
    risk_measure_review_service,
)
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.task_display import task_description_table_text
from moduly.ukoly.ui.task_dialog import TaskDialog

# Pořadí odpovídá návratovým hodnotám Task.computed_status.
_TASK_STATUS_ORDER = (
    "Aktivní",
    "Splněno - čeká na kontrolu",
    "Ukončeno",
    "Zrušeno",
)


def _task_status_sort(status: str):
    try:
        return typed_status(_TASK_STATUS_ORDER.index(status), label=status or "")
    except ValueError:
        return typed_status(len(_TASK_STATUS_ORDER), label=status or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class RiskMeasureReviewTasksWidget(QWidget):
    """Záložka Úkoly – stejný koncept jako Audit / Prověrka."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.review_id: int | None = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Úkoly lze zobrazit až po uložení přezkoumání.")
        self.info_label.setWordWrap(True)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový úkol")
        self.open_btn = QPushButton("Otevřít úkol")
        self.refresh_btn = QPushButton("Obnovit")
        toolbar.addWidget(self.new_btn)
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
        enable_typed_sorting(self.table)

        self.content_stack = QStackedWidget()
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        self.empty_label = QLabel("Přezkoumání zatím nemá žádné úkoly.")
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

        self.new_btn.clicked.connect(self.create_task)
        self.open_btn.clicked.connect(self.open_selected_task)
        self.refresh_btn.clicked.connect(self.refresh)
        self.table.doubleClicked.connect(self.open_selected_task)

        self._update_state()

    def set_review_id(self, review_id: int | None) -> None:
        self.review_id = review_id
        self.refresh()
        self._update_state()

    def refresh(self) -> None:
        tasks = []
        if self.review_id is not None:
            tasks = risk_measure_review_service.get_tasks_for_review(self.review_id)

        self.content_stack.setCurrentIndex(1 if tasks else 0)
        self.empty_label.setText(
            "Přezkoumání zatím nemá žádné úkoly."
            if self.review_id is not None
            else "Úkoly lze zobrazit až po uložení přezkoumání."
        )

        with sorting_paused(self.table):
            self.table.setRowCount(len(tasks))
            for row, task in enumerate(tasks):
                record_id = int(task.id)
                responsible = task.responsible_person or "—"
                due_display = "" if task.due_date is None else task.due_date.strftime("%d.%m.%Y")
                status = task.computed_status
                cells = [
                    create_typed_item(
                        str(task.id),
                        typed_int(task.id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        task_description_table_text(task),
                        typed_text(task_description_table_text(task)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        responsible,
                        _text_or_empty(responsible),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        due_display,
                        typed_date(task.due_date) if task.due_date is not None else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status,
                        _task_status_sort(status),
                        stable_id=record_id,
                    ),
                ]
                for column, item in enumerate(cells):
                    self.table.setItem(row, column, item)

    def create_task(self) -> None:
        if self.review_id is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_TASKS_TITLE,
                "Úkol lze založit až po uložení přezkoumání.",
            )
            return

        dialog = TaskDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data.get("title"):
            return
        try:
            risk_measure_review_service.create_task_for_review(
                self.review_id,
                title=data["title"],
                description=data.get("description") or "",
                due_date=data.get("due_date"),
                responsible_person_id=data.get("responsible_person_id"),
                workplace_id=data.get("workplace_id"),
            )
        except RiskMeasureReviewError as error:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, str(error))
            return
        self.refresh()

    def _update_state(self) -> None:
        enabled = self.review_id is not None
        self.info_label.setVisible(not enabled)
        self.new_btn.setEnabled(enabled)
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
            QMessageBox.information(self, RISK_MEASURE_REVIEW_TASKS_TITLE, "Vyberte úkol.")
            return

        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, "Úkol nebyl nalezen.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if data["title"]:
                task_service.update_task(task_id=task_id, **data)
            self.refresh()
