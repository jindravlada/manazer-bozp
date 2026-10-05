"""Editor písemné otázky."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.no_wheel_guards import NoWheelComboBox
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    ANSWER_KIND_IMAGE_LABEL,
    ANSWER_KIND_SWITCH_CONFIRM,
    ANSWER_KIND_TEXT,
    ANSWER_KIND_TEXT_LABEL,
    ANSWER_LETTERS,
    MODULE_NAME,
    QUESTION_DIALOG_TITLE_EDIT,
    QUESTION_DIALOG_TITLE_NEW,
)
from moduly.testy.modely.written_question import WrittenQuestion
from moduly.testy.sluzby.written_question_service import (
    WrittenAnswerInput,
    WrittenQuestionError,
    written_question_service,
)
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)
from moduly.testy.ui.written_question_image_slot import WrittenQuestionImageSlot


class WrittenQuestionDialog(QDialog):
    def __init__(self, parent=None, question: WrittenQuestion | None = None):
        super().__init__(parent)
        self.question_id = question.id if question is not None else None
        self.saved_question_id: int | None = self.question_id
        is_new = question is None
        self._kind = ANSWER_KIND_TEXT
        self._applying_kind = False

        self.setWindowTitle(
            QUESTION_DIALOG_TITLE_NEW if is_new else QUESTION_DIALOG_TITLE_EDIT
        )
        configure_resizable_form_dialog(
            self,
            width=720,
            height=760,
            min_width=560,
            min_height=480,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.topic = NoWheelComboBox()
        self.question_text = QPlainTextEdit()
        self.question_text.setMinimumHeight(72)
        self.question_image = WrittenQuestionImageSlot()
        self.kind_text = QRadioButton(ANSWER_KIND_TEXT_LABEL)
        self.kind_image = QRadioButton(ANSWER_KIND_IMAGE_LABEL)
        self.kind_group = QButtonGroup(self)
        self.kind_group.addButton(self.kind_text)
        self.kind_group.addButton(self.kind_image)
        self.kind_text.setChecked(True)
        kind_row = QHBoxLayout()
        kind_row.addWidget(self.kind_text)
        kind_row.addWidget(self.kind_image)
        kind_row.addStretch()
        kind_host = QWidget()
        kind_host.setLayout(kind_row)

        self.correct_group = QButtonGroup(self)
        self.correct_buttons: list[QRadioButton] = []
        self.answer_texts: list[QLineEdit] = []
        self.answer_images: list[WrittenQuestionImageSlot] = []
        answers_host = QWidget()
        answers_layout = QVBoxLayout(answers_host)
        answers_layout.setContentsMargins(0, 0, 0, 0)

        for letter in ANSWER_LETTERS:
            row = QHBoxLayout()
            radio = QRadioButton("Správná")
            self.correct_group.addButton(radio)
            self.correct_buttons.append(radio)
            label = QLabel(f"Odpověď {letter}")
            label.setMinimumWidth(88)
            text = QLineEdit()
            image = WrittenQuestionImageSlot()
            image.setVisible(False)
            self.answer_texts.append(text)
            self.answer_images.append(image)
            row.addWidget(radio)
            row.addWidget(label)
            row.addWidget(text, 1)
            row.addWidget(image, 1)
            answers_layout.addLayout(row)

        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(56)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Okruh:", self.topic)
        form.addRow("Otázka:", self.question_text)
        form.addRow("Obrázek otázky:", self.question_image)
        form.addRow("Typ odpovědí:", kind_host)
        form.addRow("", answers_host)
        form.addRow("Interní poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = create_save_cancel_box(self, is_new=is_new)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=is_new,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self._snapshot)
        self._editor.install_auto_dirty_tracking()
        self.question_image.changed.connect(self._editor.mark_dirty)
        for image in self.answer_images:
            image.changed.connect(self._editor.mark_dirty)
        self.kind_group.buttonToggled.connect(self._on_kind_toggled)
        self.correct_group.buttonToggled.connect(lambda *_args: self._editor.mark_dirty())

        self._load_topics(question.topic_id if question is not None else None)
        if question is not None:
            self._load_question(question)

        configure_form_tab_navigation(self)
        self._editor.capture_baseline()

    def accept(self) -> None:
        data = self.get_data()
        try:
            if self.question_id is None:
                created = written_question_service.create_question(**data)
                self.saved_question_id = created.id
            else:
                updated = written_question_service.update_question(
                    self.question_id,
                    **data,
                )
                self.saved_question_id = updated.id
        except WrittenQuestionError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        image_source = self.question_image.source_path()
        return {
            "topic_id": self._topic_id(),
            "text": self.question_text.toPlainText(),
            "answer_kind": self._kind,
            "answers": self._answer_inputs(),
            "question_image_source_path": image_source,
            "question_image_attachment_id": self.question_image.keep_attachment_id(),
            "note": self.note.toPlainText(),
            "active": self.active_checkbox.isChecked(),
        }

    def _snapshot(self) -> tuple:
        data = self.get_data()
        answers = tuple(
            (
                answer.text,
                answer.image_source_path,
                answer.image_attachment_id,
                answer.is_correct,
            )
            for answer in data["answers"]
        )
        return (
            data["topic_id"],
            data["text"],
            data["answer_kind"],
            answers,
            data["question_image_source_path"],
            data["question_image_attachment_id"],
            data["note"],
            data["active"],
        )

    def _answer_inputs(self) -> list[WrittenAnswerInput]:
        inputs: list[WrittenAnswerInput] = []
        for index, radio in enumerate(self.correct_buttons):
            if self._kind == ANSWER_KIND_IMAGE:
                slot = self.answer_images[index]
                inputs.append(
                    WrittenAnswerInput(
                        image_source_path=slot.source_path(),
                        image_attachment_id=slot.keep_attachment_id(),
                        is_correct=radio.isChecked(),
                    )
                )
            else:
                inputs.append(
                    WrittenAnswerInput(
                        text=self.answer_texts[index].text(),
                        is_correct=radio.isChecked(),
                    )
                )
        return inputs

    def _answers_have_content(self) -> bool:
        if self._kind == ANSWER_KIND_IMAGE:
            return any(slot.has_content() for slot in self.answer_images)
        return any(text.text().strip() for text in self.answer_texts)

    def _clear_answer_content(self) -> None:
        if self._kind == ANSWER_KIND_IMAGE:
            for slot in self.answer_images:
                slot.clear()
            return
        for text in self.answer_texts:
            text.clear()

    def _on_kind_toggled(self, _button, checked: bool) -> None:
        if self._applying_kind or not checked:
            return
        new_kind = ANSWER_KIND_TEXT if self.kind_text.isChecked() else ANSWER_KIND_IMAGE
        if new_kind == self._kind:
            return
        if self._answers_have_content():
            answer = QMessageBox.question(
                self,
                MODULE_NAME,
                ANSWER_KIND_SWITCH_CONFIRM,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._set_kind_radios(self._kind)
                return
            self._clear_answer_content()
        self._kind = new_kind
        self._apply_kind_widgets()

    def _set_kind_radios(self, kind: str) -> None:
        self._applying_kind = True
        self.kind_text.setChecked(kind == ANSWER_KIND_TEXT)
        self.kind_image.setChecked(kind == ANSWER_KIND_IMAGE)
        self._applying_kind = False

    def _apply_kind_widgets(self) -> None:
        image_mode = self._kind == ANSWER_KIND_IMAGE
        for text, slot in zip(self.answer_texts, self.answer_images, strict=True):
            text.setVisible(not image_mode)
            slot.setVisible(image_mode)

    def _topic_id(self) -> int | None:
        data = self.topic.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _load_topics(self, selected_id: int | None) -> None:
        self.topic.clear()
        self.topic.addItem("", None)
        topics = written_question_topic_service.list_topics(include_inactive=False)
        selected = (
            written_question_topic_service.get_topic(selected_id)
            if selected_id
            else None
        )
        if selected is not None and not selected.active:
            self.topic.addItem(f"{selected.name} (neaktivní)", int(selected.id))
        for topic in topics:
            self.topic.addItem(topic.name, int(topic.id))
        if selected_id is not None:
            index = self.topic.findData(int(selected_id))
            if index >= 0:
                self.topic.setCurrentIndex(index)

    def _load_question(self, question: WrittenQuestion) -> None:
        self.question_text.setPlainText(question.text)
        self.note.setPlainText(question.note or "")
        self.active_checkbox.setChecked(question.active)
        self._kind = question.answer_kind
        self._set_kind_radios(self._kind)
        self._apply_kind_widgets()
        image_path = written_question_service.attachment_path(question.image_attachment_id)
        self.question_image.set_saved(question.image_attachment_id, image_path)
        for answer, radio, text, slot in zip(
            written_question_service.get_answers(question.id),
            self.correct_buttons,
            self.answer_texts,
            self.answer_images,
            strict=True,
        ):
            radio.setChecked(bool(answer.is_correct))
            text.setText(answer.text or "")
            slot.set_saved(
                answer.image_attachment_id,
                written_question_service.attachment_path(answer.image_attachment_id),
            )
