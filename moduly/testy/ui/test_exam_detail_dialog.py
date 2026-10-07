"""Read-only detail připravené zkoušky."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    EXAM_ACTION_CLEAR_ORAL_FAILURE,
    EXAM_ACTION_RECORD_ORAL_FAILURE,
    EXAM_DETAIL_TITLE,
    EXAM_ROLE_LABELS,
    EXAM_STATUS_LABELS,
    EXAMINER_MODE_LABELS,
    MODULE_NAME,
    ORAL_FAILURE_CLEAR_CONFIRM,
    ORAL_FAILURE_CONFIRM,
    ORAL_PART_FAILED_LINE,
    written_result_label,
)

_ANSWER_CORRECT_STYLE = "color: #15803d; font-weight: 700;"
_ANSWER_ERROR_STYLE = "color: #b91c1c; font-weight: 700;"
_ANSWER_ERROR_MARK = "\u2014 chyba"
_UNANSWERED_ERROR = "Nezodpovězeno \u2014 chyba"
from moduly.testy.sluzby.test_definition_service import format_test_duration
from moduly.testy.sluzby.test_exam_service import TestExamError, format_exam_date, test_exam_service


class TestExamDetailDialog(QDialog):
    def __init__(self, parent=None, exam_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(EXAM_DETAIL_TITLE)
        self.exam_id = exam_id
        self.results_changed = False
        configure_resizable_form_dialog(
            self,
            width=860,
            height=760,
            min_width=640,
            min_height=480,
        )

        layout = QVBoxLayout(self)
        host = QWidget()
        form = QVBoxLayout(host)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addWidget(self.summary)
        self.written_summary = QLabel()
        self.written_summary.setObjectName("exam-written-summary")
        self.written_summary.setWordWrap(True)
        self.written_summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.written_summary.hide()
        form.addWidget(self.written_summary)
        self.oral_failure_button = QPushButton()
        self.oral_failure_button.setObjectName("exam-oral-failure-button")
        self.oral_failure_button.setAutoDefault(False)
        self.oral_failure_button.setDefault(False)
        self.oral_failure_button.hide()
        self.oral_failure_button.clicked.connect(self._change_oral_failure)
        form.addWidget(self.oral_failure_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.written_box = QGroupBox("Písemné otázky")
        self.written_layout = QVBoxLayout(self.written_box)
        self.oral_box = QGroupBox("Ústní otázky")
        self.oral_layout = QVBoxLayout(self.oral_box)
        form.addWidget(self.written_box)
        form.addWidget(self.oral_box)
        form.addStretch()

        layout.addWidget(wrap_in_scroll_area(host), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if exam_id is not None:
            self.load_exam(exam_id)

    def load_exam(self, exam_id: int) -> None:
        exam = test_exam_service.get_exam(exam_id)
        if exam is None:
            self.summary.setText("Zkouška nebyla nalezena.")
            self.oral_failure_button.hide()
            return
        self.exam_id = int(exam.id)
        people = test_exam_service.get_examiners(exam.id)
        commission = "\n".join(
            f"{EXAM_ROLE_LABELS.get(person.role, person.role)}: {person.display_name}"
            for person in people
        ) or EXAMINER_MODE_LABELS.get(exam.examiner_mode, "")
        written = test_exam_service.get_written_questions(exam.id)
        oral = test_exam_service.get_oral_questions(exam.id)
        self._fill_summary(exam, commission, written)
        self._fill_written_summary(exam)
        self._sync_oral_failure_button(exam)
        self._fill_written(exam, written)
        self._fill_oral(oral)
        self.written_box.setVisible(bool(exam.uses_written))
        self.oral_box.setVisible(bool(exam.uses_oral))

    def _fill_summary(self, exam, commission: str, written) -> None:
        self.summary.setText(
            "\n".join(
                [
                    f"Zaměstnanec: {exam.employee_display_name}",
                    f"Osobní číslo: {exam.employee_personal_number}",
                    f"Provoz: {exam.employee_workplace_name}",
                    f"Funkce / role: {exam.employee_roles_text}",
                    f"Test: {exam.test_name}",
                    f"Datum: {format_exam_date(exam.exam_date)}",
                    f"Platí do: {format_exam_date(exam.valid_until)}",
                    f"Stav: {EXAM_STATUS_LABELS.get(exam.status, exam.status)}",
                    f"Zkoušející / komise:\n{commission}",
                    f"Počet písemných otázek: {len(written)}",
                    f"Čas písemné části: {format_test_duration(exam.written_duration_seconds)}",
                    f"Povolené chyby: {exam.allowed_wrong_answers}",
                ]
            )
        )

    def _fill_written_summary(self, exam) -> None:
        if not exam.written_result:
            self.written_summary.clear()
            self.written_summary.hide()
            return
        lines = [
            f"Počet otázek: {exam.written_question_count}",
            f"Správně: {exam.written_correct_count}",
            f"Chybně: {exam.written_incorrect_count}",
            f"Nezodpovězeno: {exam.written_unanswered_count}",
            f"Povolené chyby: {exam.written_allowed_wrong_answers}",
            f"Výsledek písemné části: {written_result_label(exam.written_result)}",
        ]
        if exam.oral_failed_at is not None:
            lines.append(ORAL_PART_FAILED_LINE)
        lines.append(f"Výsledek zkoušky: {written_result_label(exam.exam_result)}")
        self.written_summary.setText("\n".join(lines))
        self.written_summary.show()

    def _sync_oral_failure_button(self, exam) -> None:
        action = test_exam_service.oral_failure_action(exam)
        if action == "record":
            self.oral_failure_button.setText(EXAM_ACTION_RECORD_ORAL_FAILURE)
            self.oral_failure_button.show()
            return
        if action == "clear":
            self.oral_failure_button.setText(EXAM_ACTION_CLEAR_ORAL_FAILURE)
            self.oral_failure_button.show()
            return
        self.oral_failure_button.hide()

    def _change_oral_failure(self) -> None:
        if self.exam_id is None:
            return
        exam = test_exam_service.get_exam(self.exam_id)
        action = test_exam_service.oral_failure_action(exam)
        if action == "record":
            title = EXAM_ACTION_RECORD_ORAL_FAILURE
            text = ORAL_FAILURE_CONFIRM
        elif action == "clear":
            title = EXAM_ACTION_CLEAR_ORAL_FAILURE
            text = ORAL_FAILURE_CLEAR_CONFIRM
        else:
            self._sync_oral_failure_button(exam)
            return
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if action == "record":
                test_exam_service.record_oral_failure(self.exam_id)
            else:
                test_exam_service.clear_oral_failure(self.exam_id)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self.results_changed = True
        self.load_exam(self.exam_id)

    def _fill_written(self, exam, questions) -> None:
        while self.written_layout.count():
            item = self.written_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        choices = {}
        if exam.written_result:
            choices = {
                int(choice.exam_question_id): choice
                for choice in test_exam_service.get_written_choices(exam.id)
            }
        for question in questions:
            block = QWidget()
            block.setObjectName(f"written-question-{question.position}")
            layout = QVBoxLayout(block)
            title = QLabel(
                f"{question.position}. {question.topic_name}\n{question.text}"
            )
            title.setWordWrap(True)
            title.setObjectName(f"written-text-{question.position}")
            layout.addWidget(title)
            image = self._image_label(question.image_stored_path, 280)
            if image is not None:
                image.setObjectName(f"written-image-{question.position}")
                layout.addWidget(image)
            answers = test_exam_service.get_written_answers(question.id)
            selected = None
            if exam.written_result:
                choice = choices.get(int(question.id))
                if choice is not None:
                    selected = next(
                        (
                            answer
                            for answer in answers
                            if int(answer.id) == int(choice.exam_answer_id)
                        ),
                        None,
                    )
                if selected is None:
                    missing = QLabel(_UNANSWERED_ERROR)
                    missing.setObjectName(f"written-unanswered-{question.position}")
                    missing.setStyleSheet(_ANSWER_ERROR_STYLE)
                    layout.addWidget(missing)
            for answer in answers:
                caption, style = self._answer_presentation(
                    question,
                    answer,
                    selected,
                    evaluated=bool(exam.written_result),
                )
                text = QLabel(caption)
                text.setWordWrap(True)
                text.setObjectName(f"answer-{question.position}-{answer.letter}")
                if style:
                    text.setStyleSheet(style)
                layout.addWidget(text)
                if question.answer_kind == ANSWER_KIND_IMAGE:
                    picture = self._image_label(answer.image_stored_path, 160)
                    if picture is not None:
                        picture.setObjectName(
                            f"answer-image-{question.position}-{answer.letter}"
                        )
                        layout.addWidget(picture)
            self.written_layout.addWidget(block)

    def _answer_presentation(self, question, answer, selected, *, evaluated: bool) -> tuple[str, str]:
        body = f"{answer.letter})"
        if question.answer_kind != ANSWER_KIND_IMAGE and str(answer.text or "").strip():
            body = f"{answer.letter}) {answer.text}"
        if not evaluated:
            return body, ""
        chosen = selected is not None and int(answer.id) == int(selected.id)
        if chosen and answer.is_correct:
            return body, _ANSWER_CORRECT_STYLE
        if chosen:
            return f"{body} {_ANSWER_ERROR_MARK}", _ANSWER_ERROR_STYLE
        if answer.is_correct and (selected is None or not selected.is_correct):
            return body, _ANSWER_CORRECT_STYLE
        return body, ""

    def _fill_oral(self, questions) -> None:
        while self.oral_layout.count():
            item = self.oral_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for question in questions:
            label = QLabel(f"{question.position}. {question.topic_name}\n{question.text}")
            label.setWordWrap(True)
            label.setObjectName(f"oral-text-{question.position}")
            self.oral_layout.addWidget(label)

    def _image_label(self, relative_path: str, width: int) -> QLabel | None:
        path = test_exam_service.resolve_snapshot_image(relative_path)
        if path is None:
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        label = QLabel()
        label.setPixmap(
            pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        )
        return label
