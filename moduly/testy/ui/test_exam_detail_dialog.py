"""Read-only detail připravené zkoušky."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    EXAM_DETAIL_TITLE,
    EXAM_ROLE_LABELS,
    EXAM_STATUS_LABELS,
    EXAMINER_MODE_LABELS,
    WRITTEN_OUTCOME_CORRECT,
    WRITTEN_OUTCOME_INCORRECT,
    WRITTEN_OUTCOME_LABELS,
    WRITTEN_OUTCOME_UNANSWERED,
    written_result_label,
)
from moduly.testy.sluzby.test_definition_service import format_test_duration
from moduly.testy.sluzby.test_exam_service import format_exam_date, test_exam_service


class TestExamDetailDialog(QDialog):
    def __init__(self, parent=None, exam_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(EXAM_DETAIL_TITLE)
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
            return
        people = test_exam_service.get_examiners(exam.id)
        commission = "\n".join(
            f"{EXAM_ROLE_LABELS.get(person.role, person.role)}: {person.display_name}"
            for person in people
        ) or EXAMINER_MODE_LABELS.get(exam.examiner_mode, "")
        written = test_exam_service.get_written_questions(exam.id)
        oral = test_exam_service.get_oral_questions(exam.id)
        self._fill_summary(exam, commission, written)
        self._fill_written_summary(exam)
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
        self.written_summary.setText(
            "\n".join(
                [
                    f"Počet otázek: {exam.written_question_count}",
                    f"Správně: {exam.written_correct_count}",
                    f"Chybně: {exam.written_incorrect_count}",
                    f"Nezodpovězeno: {exam.written_unanswered_count}",
                    f"Povolené chyby: {exam.written_allowed_wrong_answers}",
                    f"Výsledek písemné části: {written_result_label(exam.written_result)}",
                    f"Výsledek zkoušky: {written_result_label(exam.exam_result)}",
                ]
            )
        )
        self.written_summary.show()

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
            if exam.written_result:
                layout.addWidget(self._question_verdict(question, answers, choices))
            answers_form = QFormLayout()
            for answer in answers:
                mark = " (správná)" if answer.is_correct else ""
                if question.answer_kind == ANSWER_KIND_IMAGE:
                    host = QWidget()
                    host_layout = QVBoxLayout(host)
                    host_layout.setContentsMargins(0, 0, 0, 0)
                    host_layout.addWidget(QLabel(mark.strip() or " "))
                    picture = self._image_label(answer.image_stored_path, 160)
                    if picture is not None:
                        picture.setObjectName(f"answer-image-{question.position}-{answer.letter}")
                        host_layout.addWidget(picture)
                    answers_form.addRow(f"{answer.letter})", host)
                else:
                    text = QLabel(f"{answer.text}{mark}")
                    text.setWordWrap(True)
                    text.setObjectName(f"answer-{question.position}-{answer.letter}")
                    answers_form.addRow(f"{answer.letter})", text)
            layout.addLayout(answers_form)
            self.written_layout.addWidget(block)

    def _question_verdict(self, question, answers, choices) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        choice = choices.get(int(question.id))
        selected = None
        if choice is not None:
            selected = next(
                (answer for answer in answers if int(answer.id) == int(choice.exam_answer_id)),
                None,
            )
        correct = next((answer for answer in answers if answer.is_correct), None)
        if selected is None:
            outcome = WRITTEN_OUTCOME_UNANSWERED
        elif selected.is_correct:
            outcome = WRITTEN_OUTCOME_CORRECT
        else:
            outcome = WRITTEN_OUTCOME_INCORRECT
        verdict = QLabel(f"Vyhodnocení: {WRITTEN_OUTCOME_LABELS[outcome]}")
        verdict.setObjectName(f"written-outcome-{question.position}")
        verdict.setStyleSheet(self._outcome_style(outcome))
        employee = QLabel(
            "Odpověď zaměstnance: "
            + (
                "nezodpovězeno"
                if selected is None
                else self._answer_caption(question, selected)
            )
        )
        employee.setWordWrap(True)
        employee.setObjectName(f"written-employee-answer-{question.position}")
        correct_label = QLabel(
            "Správná odpověď: "
            + (self._answer_caption(question, correct) if correct is not None else "není ve snapshotu")
        )
        correct_label.setWordWrap(True)
        correct_label.setObjectName(f"written-correct-answer-{question.position}")
        layout.addWidget(verdict)
        layout.addWidget(employee)
        layout.addWidget(correct_label)
        return host

    def _answer_caption(self, question, answer) -> str:
        if question.answer_kind == ANSWER_KIND_IMAGE or not str(answer.text or "").strip():
            return f"{answer.letter})"
        return f"{answer.letter}) {answer.text}"

    def _outcome_style(self, outcome: str) -> str:
        if outcome == WRITTEN_OUTCOME_CORRECT:
            return "color: #14532d; font-weight: 700;"
        if outcome == WRITTEN_OUTCOME_INCORRECT:
            return "color: #991b1b; font-weight: 700;"
        return "color: #57534e; font-weight: 700;"

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
