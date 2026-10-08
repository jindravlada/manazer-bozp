"""Read-only detail připravené zkoušky."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.export.open_export import open_local_file
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    EXAM_ACTION_CLEAR_ORAL_FAILURE,
    EXAM_ACTION_RECORD_ORAL_FAILURE,
    EXAM_DETAIL_TITLE,
    EXAM_PROTOCOL_ACTION_ATTACH,
    EXAM_PROTOCOL_ACTION_OPEN,
    EXAM_PROTOCOL_ACTION_REMOVE,
    EXAM_PROTOCOL_ACTION_REPLACE,
    EXAM_PROTOCOL_ATTACHED,
    EXAM_PROTOCOL_FILE_FILTER,
    EXAM_PROTOCOL_MISSING,
    EXAM_PROTOCOL_REMOVE_CONFIRM,
    EXAM_PROTOCOL_REPLACE_CONFIRM,
    EXAM_PROTOCOL_SECTION,
    EXAM_ROLE_LABELS,
    EXAM_STATUS_COMPLETED,
    EXAM_STATUS_LABELS,
    EXAMINER_MODE_LABELS,
    MODULE_NAME,
    ORAL_FAILURE_CLEAR_CONFIRM,
    ORAL_FAILURE_CONFIRM,
    ORAL_PART_FAILED_LINE,
    written_result_label,
)

from moduly.testy.sluzby.exam_signed_protocol_service import (
    ExamSignedProtocolError,
    exam_signed_protocol_service,
)
from moduly.testy.sluzby.test_definition_service import format_test_duration
from moduly.testy.sluzby.test_exam_service import (
    TestExamError,
    format_exam_date,
    snapshot_image_notice,
    test_exam_service,
)
from moduly.testy.sluzby.written_answer_presentation import (
    UNANSWERED_ERROR,
    present_answer,
    qt_answer_style,
    selected_answer,
)


class TestExamDetailDialog(QDialog):
    def __init__(self, parent=None, exam_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(EXAM_DETAIL_TITLE)
        self.exam_id = exam_id
        self.results_changed = False
        self.protocol_changed = False
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
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
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

        self.protocol_box = QGroupBox(EXAM_PROTOCOL_SECTION)
        protocol_layout = QVBoxLayout(self.protocol_box)
        self.protocol_status = QLabel(EXAM_PROTOCOL_MISSING)
        self.protocol_status.setObjectName("exam-protocol-status")
        protocol_layout.addWidget(self.protocol_status)
        protocol_actions = QHBoxLayout()
        self.protocol_attach_btn = self._protocol_button(
            EXAM_PROTOCOL_ACTION_ATTACH,
            "exam-protocol-attach",
            self._attach_protocol,
        )
        self.protocol_open_btn = self._protocol_button(
            EXAM_PROTOCOL_ACTION_OPEN,
            "exam-protocol-open",
            self._open_protocol,
        )
        self.protocol_replace_btn = self._protocol_button(
            EXAM_PROTOCOL_ACTION_REPLACE,
            "exam-protocol-replace",
            self._replace_protocol,
        )
        self.protocol_remove_btn = self._protocol_button(
            EXAM_PROTOCOL_ACTION_REMOVE,
            "exam-protocol-remove",
            self._remove_protocol,
        )
        for button in (
            self.protocol_attach_btn,
            self.protocol_open_btn,
            self.protocol_replace_btn,
            self.protocol_remove_btn,
        ):
            protocol_actions.addWidget(button)
        protocol_actions.addStretch()
        protocol_layout.addLayout(protocol_actions)
        form.addWidget(self.protocol_box)

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
            self._show_protocol(completed=False, attached=False)
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
        self._sync_protocol(exam)
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

    def _protocol_button(self, text: str, object_name: str, handler) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setEnabled(False)
        button.clicked.connect(handler)
        return button

    def _sync_protocol(self, exam) -> None:
        try:
            state = exam_signed_protocol_service.describe(int(exam.id))
        except ExamSignedProtocolError:
            state = None
        attached = bool(state and state.attached)
        self._show_protocol(
            completed=exam.status == EXAM_STATUS_COMPLETED,
            attached=attached,
        )

    def _show_protocol(self, *, completed: bool, attached: bool) -> None:
        self.protocol_status.setText(
            EXAM_PROTOCOL_ATTACHED if attached else EXAM_PROTOCOL_MISSING
        )
        self.protocol_attach_btn.setEnabled(completed and not attached)
        self.protocol_open_btn.setEnabled(attached)
        self.protocol_replace_btn.setEnabled(completed and attached)
        self.protocol_remove_btn.setEnabled(attached)

    def _choose_pdf(self, title: str) -> str:
        chosen, _selected_filter = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            EXAM_PROTOCOL_FILE_FILTER,
        )
        return str(chosen or "")

    def _attach_protocol(self) -> None:
        if self.exam_id is None:
            return
        chosen = self._choose_pdf(EXAM_PROTOCOL_ACTION_ATTACH)
        if not chosen:
            return
        self._store_protocol(chosen, replace=False)

    def _replace_protocol(self) -> None:
        if self.exam_id is None:
            return
        answer = QMessageBox.question(
            self,
            EXAM_PROTOCOL_ACTION_REPLACE,
            EXAM_PROTOCOL_REPLACE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        chosen = self._choose_pdf(EXAM_PROTOCOL_ACTION_REPLACE)
        if not chosen:
            return
        self._store_protocol(chosen, replace=True)

    def _store_protocol(self, chosen: str, *, replace: bool) -> None:
        try:
            if replace:
                exam_signed_protocol_service.replace(int(self.exam_id), chosen)
            else:
                exam_signed_protocol_service.attach(int(self.exam_id), chosen)
        except ExamSignedProtocolError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self.protocol_changed = True
        self.load_exam(int(self.exam_id))

    def _open_protocol(self) -> None:
        if self.exam_id is None:
            return
        try:
            path = exam_signed_protocol_service.validated_copy_path(int(self.exam_id))
        except ExamSignedProtocolError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        open_local_file(
            path,
            parent=self,
            title=EXAM_PROTOCOL_SECTION,
            show_error=True,
        )

    def _remove_protocol(self) -> None:
        if self.exam_id is None:
            return
        answer = QMessageBox.question(
            self,
            EXAM_PROTOCOL_ACTION_REMOVE,
            EXAM_PROTOCOL_REMOVE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            exam_signed_protocol_service.detach(int(self.exam_id))
        except ExamSignedProtocolError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self.protocol_changed = True
        self.load_exam(int(self.exam_id))

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
            title = QLabel()
            title.setTextFormat(Qt.TextFormat.PlainText)
            title.setText(f"{question.position}. {question.topic_name}\n{question.text}")
            title.setWordWrap(True)
            title.setObjectName(f"written-text-{question.position}")
            layout.addWidget(title)
            image = self._image_label(
                question.image_stored_path,
                question.image_sha256,
                280,
                f"written-image-{question.position}",
            )
            if image is not None:
                layout.addWidget(image)
            answers = test_exam_service.get_written_answers(question.id)
            selected = None
            if exam.written_result:
                selected = selected_answer(answers, choices.get(int(question.id)))
                if selected is None:
                    missing = QLabel(UNANSWERED_ERROR)
                    missing.setObjectName(f"written-unanswered-{question.position}")
                    missing.setStyleSheet(qt_answer_style("error"))
                    layout.addWidget(missing)
            for answer in answers:
                caption, tone = present_answer(
                    question,
                    answer,
                    selected,
                    evaluated=bool(exam.written_result),
                )
                style = qt_answer_style(tone)
                text = QLabel()
                text.setTextFormat(Qt.TextFormat.PlainText)
                text.setText(caption)
                text.setWordWrap(True)
                text.setObjectName(f"answer-{question.position}-{answer.letter}")
                if style:
                    text.setStyleSheet(style)
                layout.addWidget(text)
                if question.answer_kind == ANSWER_KIND_IMAGE:
                    picture = self._image_label(
                        answer.image_stored_path,
                        answer.image_sha256,
                        160,
                        f"answer-image-{question.position}-{answer.letter}",
                    )
                    if picture is not None:
                        layout.addWidget(picture)
            self.written_layout.addWidget(block)

    def _fill_oral(self, questions) -> None:
        while self.oral_layout.count():
            item = self.oral_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for question in questions:
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setText(f"{question.position}. {question.topic_name}\n{question.text}")
            label.setWordWrap(True)
            label.setObjectName(f"oral-text-{question.position}")
            self.oral_layout.addWidget(label)

    def _image_label(
        self,
        relative_path: str,
        expected_sha256: str,
        width: int,
        object_name: str,
    ) -> QLabel | None:
        loaded = test_exam_service.load_snapshot_image(relative_path, expected_sha256)
        notice = snapshot_image_notice(loaded.status)
        label = QLabel()
        label.setObjectName(object_name if not notice else f"{object_name}-notice")
        if notice:
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setText(notice)
            return label
        if not loaded.data:
            return None
        pixmap = QPixmap()
        if not pixmap.loadFromData(loaded.data):
            return None
        label.setPixmap(
            pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        )
        return label
