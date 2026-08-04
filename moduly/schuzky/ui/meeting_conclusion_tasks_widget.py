"""Sekce Úkoly ze závěrů / Navázané úkoly v editoru schůzky."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_MEETING
from moduly.schuzky.constants import (
    ACTION_CREATE_TASK,
    ACTION_OPEN_TASK,
    DIALOG_WINDOW_TITLE,
    SAVE_MEETING_BEFORE_TASK_MESSAGE,
    SECTION_CONCLUSION_TASKS,
    SECTION_LINKED_TASKS,
)
from moduly.schuzky.sluzby.meeting_conclusion_tasks import (
    ConclusionTaskRow,
    build_conclusion_task_view,
    conclusion_check_code,
)
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class MeetingConclusionTasksWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._meeting_id: int | None = None
        self._get_conclusions_text = lambda: ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._header = QLabel(SECTION_CONCLUSION_TASKS)
        header_font = QFont(self._header.font())
        header_font.setBold(True)
        self._header.setFont(header_font)
        layout.addWidget(self._header)

        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        layout.addWidget(self._rows_host)

        self._empty_label = QLabel("Žádné body závěrů.")
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._orphan_header = QLabel(SECTION_LINKED_TASKS)
        orphan_font = QFont(self._orphan_header.font())
        orphan_font.setBold(True)
        self._orphan_header.setFont(orphan_font)
        layout.addWidget(self._orphan_header)

        self._orphan_host = QWidget()
        self._orphan_layout = QVBoxLayout(self._orphan_host)
        self._orphan_layout.setContentsMargins(0, 0, 0, 0)
        self._orphan_layout.setSpacing(6)
        layout.addWidget(self._orphan_host)

        self._orphan_header.hide()
        self._orphan_host.hide()

    def configure(self, *, meeting_id: int | None, get_conclusions_text) -> None:
        self._meeting_id = meeting_id
        self._get_conclusions_text = get_conclusions_text
        self.refresh()

    def set_meeting_id(self, meeting_id: int | None) -> None:
        self._meeting_id = meeting_id
        self.refresh()

    def refresh(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        while self._orphan_layout.count():
            item = self._orphan_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        view = build_conclusion_task_view(
            self._get_conclusions_text(),
            meeting_id=self._meeting_id,
        )

        if not view.rows:
            self._empty_label.show()
            self._rows_host.hide()
        else:
            self._empty_label.hide()
            self._rows_host.show()
            for row in view.rows:
                self._rows_layout.addWidget(self._build_conclusion_row(row))

        if view.orphan_tasks:
            self._orphan_header.show()
            self._orphan_host.show()
            for task in view.orphan_tasks:
                self._orphan_layout.addWidget(self._build_orphan_row(task))
        else:
            self._orphan_header.hide()
            self._orphan_host.hide()

    def _build_conclusion_row(self, row: ConclusionTaskRow) -> QWidget:
        frame = QWidget()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        text_label = QLabel(row.text)
        text_label.setWordWrap(True)
        text_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(text_label, 1)

        if row.task is not None:
            status = getattr(row.task, "computed_status", None) or row.task.status or ""
            if status:
                status_label = QLabel(status)
                status_label.setStyleSheet("color: #555;")
                layout.addWidget(status_label)
            button = QPushButton(ACTION_OPEN_TASK)
            button.clicked.connect(
                lambda *_args, task_id=row.task.id: self._open_task(task_id)
            )
        else:
            button = QPushButton(ACTION_CREATE_TASK)
            button.clicked.connect(
                lambda *_args, text=row.text: self._create_task(text)
            )
        layout.addWidget(button)
        return frame

    def _build_orphan_row(self, task) -> QWidget:
        frame = QWidget()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = (task.title or "").strip() or f"Úkol #{task.id}"
        text_label = QLabel(title)
        text_label.setWordWrap(True)
        layout.addWidget(text_label, 1)

        status = getattr(task, "computed_status", None) or task.status or ""
        if status:
            status_label = QLabel(status)
            status_label.setStyleSheet("color: #555;")
            layout.addWidget(status_label)

        button = QPushButton(ACTION_OPEN_TASK)
        button.clicked.connect(lambda *_args, task_id=task.id: self._open_task(task_id))
        layout.addWidget(button)
        return frame

    def _create_task(self, conclusion_text: str) -> None:
        if self._meeting_id is None:
            QMessageBox.information(
                self,
                DIALOG_WINDOW_TITLE,
                SAVE_MEETING_BEFORE_TASK_MESSAGE,
            )
            return

        dialog = TaskDialog(self)
        dialog.title_edit.setPlainText(conclusion_text)
        if dialog.exec() != QDialog.Accepted:
            return

        data = dialog.get_data()
        title = (data.get("title") or "").strip()
        if not title:
            title = conclusion_text
        task_service.create_task(
            title=title,
            description=data.get("description") or "",
            priority=data.get("priority") or "Normální",
            due_date=data.get("due_date"),
            responsible_person_id=data.get("responsible_person_id"),
            workplace_id=data.get("workplace_id"),
            completed=bool(data.get("completed")),
            completed_date=data.get("completed_date"),
            check_due_date=data.get("check_due_date"),
            checked_date=data.get("checked_date"),
            checked_by_id=data.get("checked_by_id"),
            canceled=bool(data.get("canceled")),
            note=data.get("note") or "",
            requires_verification=data.get("requires_verification"),
            source_module=ENTITY_MEETING,
            source_record_id=self._meeting_id,
            source_check_code=conclusion_check_code(conclusion_text),
        )
        self.refresh()

    def _open_task(self, task_id: int) -> None:
        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, "Úkol nebyl nalezen.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec() == QDialog.Accepted:
            task_service.update_task(task_id, **dialog.get_data())
        self.refresh()
