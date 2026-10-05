"""Editor ústní otázky."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QMessageBox,
    QPlainTextEdit,
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
    MODULE_NAME,
    QUESTION_DIALOG_TITLE_EDIT,
    QUESTION_DIALOG_TITLE_NEW,
)
from moduly.testy.modely.oral_question import OralQuestion
from moduly.testy.sluzby.oral_question_service import (
    OralQuestionError,
    oral_question_service,
)
from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service


class OralQuestionDialog(QDialog):
    def __init__(self, parent=None, question: OralQuestion | None = None):
        super().__init__(parent)
        self.question_id = question.id if question is not None else None
        self.saved_question_id: int | None = self.question_id
        is_new = question is None

        self.setWindowTitle(
            QUESTION_DIALOG_TITLE_NEW if is_new else QUESTION_DIALOG_TITLE_EDIT
        )
        configure_resizable_form_dialog(
            self,
            width=640,
            height=520,
            min_width=480,
            min_height=360,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.topic = NoWheelComboBox()
        self.question_text = QPlainTextEdit()
        self.question_text.setMinimumHeight(96)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(72)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Okruh:", self.topic)
        form.addRow("Otázka:", self.question_text)
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

        selected_topic_id = question.topic_id if question is not None else None
        self._load_topics(selected_topic_id)
        if question is not None:
            self.question_text.setPlainText(question.text)
            self.note.setPlainText(question.note or "")
            self.active_checkbox.setChecked(question.active)

        configure_form_tab_navigation(self)
        self._editor.capture_baseline()

    def accept(self) -> None:
        data = self.get_data()
        try:
            if self.question_id is None:
                created = oral_question_service.create_question(**data)
                self.saved_question_id = created.id
            else:
                updated = oral_question_service.update_question(self.question_id, **data)
                self.saved_question_id = updated.id
        except OralQuestionError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "topic_id": self._topic_id(),
            "text": self.question_text.toPlainText(),
            "note": self.note.toPlainText(),
            "active": self.active_checkbox.isChecked(),
        }

    def _snapshot(self) -> tuple:
        return (
            self._topic_id(),
            self.question_text.toPlainText(),
            self.note.toPlainText(),
            self.active_checkbox.isChecked(),
        )

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
        topics = oral_question_topic_service.list_topics(include_inactive=False)
        selected = (
            oral_question_topic_service.get_topic(selected_id) if selected_id else None
        )
        if selected is not None and not selected.active:
            self.topic.addItem(f"{selected.name} (neaktivní)", int(selected.id))
        for topic in topics:
            self.topic.addItem(topic.name, int(topic.id))
        if selected_id is not None:
            index = self.topic.findData(int(selected_id))
            if index >= 0:
                self.topic.setCurrentIndex(index)
