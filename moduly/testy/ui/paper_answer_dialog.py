"""Přepis odpovědí A/B/C z odevzdaného papírového testu."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_perform_action_button
from moduly.testy.constants import (
    EXAM_ACTION_EVALUATE_PAPER,
    MODULE_NAME,
    PAPER_EVALUATE_CONFIRM,
    PAPER_EVALUATE_INCOMPLETE,
)
from moduly.testy.sluzby.paper_test_export_service import variant_label
from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
from moduly.testy.sluzby.written_exam_service import written_exam_service

_LETTER_KEYS = {
    Qt.Key.Key_A: "A",
    Qt.Key.Key_B: "B",
    Qt.Key.Key_C: "C",
}


class PaperAnswerDialog(QDialog):
    def __init__(self, exam_id: int, parent=None):
        super().__init__(parent)
        self.exam_id = int(exam_id)
        self.evaluated = False
        self.setWindowTitle("Zadat odpovědi z papírového testu")
        self.resize(460, 560)

        exam = test_exam_service.get_exam(self.exam_id)
        if exam is None:
            raise TestExamError("Zkouška nebyla nalezena.")
        self._variant = variant_label(exam)

        layout = QVBoxLayout(self)
        self.variant = QLabel(self._variant)
        self.variant.setObjectName("paper-variant-label")
        self.variant.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.employee = QLabel()
        self.employee.setTextFormat(Qt.TextFormat.PlainText)
        self.employee.setText(exam.employee_display_name)
        self.employee.setObjectName("paper-employee-label")
        self.employee.setStyleSheet("font-size: 15px;")
        self.test_name = QLabel()
        self.test_name.setTextFormat(Qt.TextFormat.PlainText)
        self.test_name.setText(exam.test_name)
        self.test_name.setObjectName("paper-test-label")
        self.test_name.setWordWrap(True)
        self.test_name.setStyleSheet("font-size: 15px;")
        self.count = QLabel()
        self.count.setObjectName("paper-count-label")
        self.count.setStyleSheet("font-size: 15px;")
        self.position = QLabel()
        self.position.setObjectName("paper-position-label")
        self.position.setStyleSheet("font-size: 16px; font-weight: 700; color: #1d4ed8;")
        hint = QLabel(
            "Zadejte A, B nebo C. Delete nebo Backspace smaže odpověď aktuální otázky."
        )
        hint.setWordWrap(True)
        hint.setObjectName("paper-entry-hint")

        self.list = QListWidget()
        self.list.setObjectName("paper-answer-list")
        self.list.setStyleSheet(
            "QListWidget { font-size: 18px; }"
            "QListWidget::item { padding: 8px; }"
            "QListWidget::item:selected { background: #1d4ed8; color: white; }"
        )
        self.list.currentRowChanged.connect(self._show_position)
        self.list.installEventFilter(self)

        self.evaluate_btn = QPushButton(EXAM_ACTION_EVALUATE_PAPER)
        self.evaluate_btn.setObjectName("paper-evaluate-button")
        configure_perform_action_button(self.evaluate_btn)
        self.evaluate_btn.clicked.connect(self.evaluate)
        self.evaluate_btn.setAutoDefault(False)
        self.evaluate_btn.setDefault(False)
        self.evaluate_btn.installEventFilter(self)
        close_btn = QPushButton("Zavřít")
        close_btn.setAutoDefault(False)
        close_btn.clicked.connect(self.reject)
        close_btn.installEventFilter(self)

        layout.addWidget(self.variant)
        layout.addWidget(self.employee)
        layout.addWidget(self.test_name)
        layout.addWidget(self.count)
        layout.addWidget(self.position)
        layout.addWidget(hint)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.evaluate_btn)
        layout.addWidget(close_btn)

        self._reload(self._continue_row())
        self.list.setFocus()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if self._on_key(event):
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._on_key(event):
            return
        super().keyPressEvent(event)

    def evaluate(self) -> None:
        sheet = written_exam_service.paper_sheet(self.exam_id)
        blank = sum(1 for line in sheet.lines if not line.letter)
        text = PAPER_EVALUATE_INCOMPLETE if blank else PAPER_EVALUATE_CONFIRM
        answer = QMessageBox.question(
            self,
            EXAM_ACTION_EVALUATE_PAPER,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            written_exam_service.evaluate_paper(self.exam_id)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self.evaluated = True
        self.accept()

    def _on_key(self, event: QKeyEvent) -> bool:
        letter = _LETTER_KEYS.get(event.key())
        text = event.text()
        if letter is None and text and len(text) == 1 and text.casefold() in {"a", "b", "c"}:
            letter = text.upper()
        if letter is not None:
            self._enter(letter)
            return True
        if text and len(text) == 1 and text.isalpha():
            return True
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._clear()
            return True
        if event.key() == Qt.Key.Key_Up:
            self._move(-1)
            return True
        if event.key() == Qt.Key.Key_Down:
            self._move(1)
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return True
        return False

    def _enter(self, letter: str) -> None:
        row = self.list.currentRow()
        if row < 0 or row >= len(self.sheet.lines):
            return
        line = self.sheet.lines[row]
        try:
            written_exam_service.save_paper_letter(
                self.exam_id,
                line.exam_question_id,
                letter,
            )
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self._reload(min(row + 1, len(self.sheet.lines) - 1))

    def _clear(self) -> None:
        row = self.list.currentRow()
        if row < 0 or row >= len(self.sheet.lines):
            return
        line = self.sheet.lines[row]
        try:
            written_exam_service.clear_paper_answer(self.exam_id, line.exam_question_id)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self._reload(row)

    def _move(self, step: int) -> None:
        count = self.list.count()
        if count <= 0:
            return
        row = self.list.currentRow()
        if row < 0:
            row = 0
        self.list.setCurrentRow(max(0, min(count - 1, row + step)))

    def _continue_row(self) -> int:
        sheet = written_exam_service.paper_sheet(self.exam_id)
        for index, line in enumerate(sheet.lines):
            if not line.letter:
                return index
        return max(0, len(sheet.lines) - 1)

    def _reload(self, select: int) -> None:
        self.sheet = written_exam_service.paper_sheet(self.exam_id)
        self.count.setText(f"Počet otázek: {self.sheet.question_count}")
        self.list.blockSignals(True)
        self.list.clear()
        for line in self.sheet.lines:
            item = QListWidgetItem(f"{line.position}. {line.letter or '—'}")
            item.setData(Qt.ItemDataRole.UserRole, line.exam_question_id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(max(0, min(select, self.list.count() - 1)))
        self.list.blockSignals(False)
        self._show_position()

    def _show_position(self, _row: int = -1) -> None:
        row = self.list.currentRow()
        if row < 0 or row >= len(self.sheet.lines):
            self.position.setText("")
            return
        self.position.setText(f"Aktuální otázka: {self.sheet.lines[row].position}")
